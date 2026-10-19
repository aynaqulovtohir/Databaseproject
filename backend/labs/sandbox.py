"""Virtual laboratoriya uchun "qum quti": talaba SQL kodini xavfsiz ishga tushirish.

Kod asosiy bazada emas, alohida `lab_sandbox` bazasida bajariladi. Har bir ishga
tushirish uchun bir martalik rol va shu rolga tegishli sxema yaratiladi, ish
tugagach ikkalasi ham o'chiriladi. Shu sababli talaba kodi:
- platformaning o'z jadvallarini (foydalanuvchilar, baholar) ko'ra olmaydi;
- boshqa talabaning ishiga ta'sir qilmaydi;
- vaqt, natija hajmi va vaqtinchalik fayllar hajmi bo'yicha cheklangan;
- serverdagi boshqa bazalarga ulana olmaydi, rollar, bazalar, sessiyalar va server
  sozlamalari ro'yxatini ko'ra olmaydi.
Xotira sarfini (work_mem) PostgreSQL ichida cheklab bo'lmaydi, shuning uchun qum quti
alohida, resurslari cheklangan serverda (docker-compose'dagi lab_db) ishlatiladi.
"""
import logging
import re
import secrets
import select
import threading
import time
import uuid
from dataclasses import dataclass, field

import psycopg
from django.conf import settings
from psycopg import pq, sql

logger = logging.getLogger(__name__)

# Bitta SQL buyruq uchun vaqt (ms) va butun skript uchun umumiy vaqt (soniya)
STATEMENT_TIMEOUT_MS = 5000
SCRIPT_TIMEOUT_SECONDS = 10
# Solishtirish uchun saqlanadigan va serverdan qabul qilinadigan qatorlar chegarasi
MAX_KEPT_ROWS = 1000
MAX_RECEIVED_ROWS = 20_000
MAX_CELL_LENGTH = 2000
ROLE_PREFIX = "labrun_"
# Bitta ishga tushirishning vaqtinchalik fayllari (katta saralash, hash) uchun disk chegarasi.
# Bu sozlamani faqat superuser o'zgartira oladi, talaba kodi uni oshira olmaydi.
TEMP_FILE_LIMIT = "64MB"
# Qum quti bazasi va vaqtinchalik fayllarning umumiy disk chegarasi. Server ma'lumotlari tmpfs'da (512m);
# PostgreSQL'da sxema bo'yicha kvota yo'q, shuning uchun kod bajarilayotganda hajm muntazam tekshiriladi va
# oshsa, kod to'xtatiladi: aks holda bitta talaba bir necha soniyada diskni to'ldirib, hammaga xalaqit beradi
MAX_STORAGE_BYTES = 256 * 1024 * 1024
STORAGE_CHECK_SECONDS = 0.5
# Talaba rolidan yopiladigan tizim ro'yxatlari: ular laboratoriya uchun kerak emas,
# lekin serverdagi boshqa bazalar, foydalanuvchilar va sessiyalar haqida ma'lumot beradi
HIDDEN_CATALOG_VIEWS = (
    "pg_roles",
    "pg_user",
    "pg_auth_members",
    "pg_database",
    "pg_stat_activity",
    "pg_settings",
    "pg_stat_ssl",
    "pg_stat_gssapi",
)
# Bir vaqtda bir nechta jarayon bazani sozlamasligi uchun advisory lock kaliti
HARDENING_LOCK_KEY = 7_401_202
# Laboratoriyalar uchun kengaytmalar (masalan, pgvector — vektorli qidiruv) shu sxemaga o'rnatiladi. Talaba roli
# unda faqat USAGE huquqiga ega: turlar va operatorlardan foydalana oladi, lekin hech narsa yarata olmaydi.
# Server obrazida kengaytma bo'lmasa (oddiy postgres), laboratoriyalar kengaytmasiz ishlayveradi
EXTENSION_SCHEMA = "ext"
EXTENSIONS = ("vector",)

_database_ready = False
_database_lock = threading.Lock()
_extensions_checked = False


class SandboxUnavailable(Exception):
    """Qum quti bazasiga ulanib bo'lmadi (talaba kodidagi xato emas)."""


@dataclass
class SqlError:
    message: str
    sqlstate: str = ""
    detail: str = ""
    hint: str = ""
    # Xato joylashgan qator (1 dan boshlab); aniqlab bo'lmasa None
    line: int | None = None


@dataclass
class RowSet:
    columns: list[str]
    rows: list[tuple] = field(default_factory=list)
    row_count: int = 0

    @property
    def truncated(self):
        return self.row_count > len(self.rows)


@dataclass
class TableState:
    # ustun nomi -> (tur, NOT NULL)
    columns: dict[str, tuple[str, bool]]
    # Cheklovlar matni, masalan "PRIMARY KEY (id)"
    constraints: list[str]
    # Qatorlar (ustunlar nomi bo'yicha tartiblangan), saralangan
    rows: list[str]
    rows_truncated: bool = False


@dataclass
class PlanNode:
    node_type: str
    relation: str = ""
    index: str = ""


@dataclass
class RunOutcome:
    error: SqlError | None = None
    # Oxirgi natija qaytargan buyruq (odatda SELECT) natijasi
    result: RowSet | None = None
    # Oxirgi buyruq holati, masalan "CREATE TABLE" yoki "INSERT 0 3"
    status_message: str = ""
    # Skriptdan keyingi jadvallar holati: jadval nomi -> TableState
    tables: dict[str, TableState] = field(default_factory=dict)
    # True bo'lsa, xato talaba kodida emas, boshlang'ich jadvallarda (setup_sql)
    setup_failed: bool = False
    # explain_sql berilganda: so'rov rejasi (EXPLAIN, xarajatlarsiz) qatorlari va rejadagi tugunlar
    plan: list[str] = field(default_factory=list)
    plan_nodes: list[PlanNode] = field(default_factory=list)
    # Rejalashtiruvchi baholagan umumiy narx (shartli birlik): taqqoslash uchun
    plan_cost: float | None = None
    # Rejani olib bo'lmadi (masalan, talaba jadvalni o'chirib yuborgan)
    plan_error: SqlError | None = None


def _connect(dbname, **overrides):
    database = settings.LAB_DB
    params = {
        "host": database["HOST"],
        "port": database["PORT"],
        "user": database["USER"],
        "password": database["PASSWORD"],
        "dbname": dbname,
        "connect_timeout": 5,
        "autocommit": True,
    }
    params.update(overrides)
    try:
        return psycopg.connect(**params)
    except psycopg.OperationalError as exc:
        raise SandboxUnavailable(str(exc)) from exc


def ping():
    """Laboratoriya bazasi serveri javob beryaptimi (monitoring uchun). Ishlamasa SandboxUnavailable."""
    with _connect(settings.LAB_DB["MAINTENANCE_DB"]) as connection:
        connection.execute("SELECT 1")


def _ensure_database():
    """Qum quti bazasini birinchi murojaatda yaratadi."""
    global _database_ready
    if _database_ready:
        return
    with _database_lock:
        if _database_ready:
            return
        name = settings.LAB_SANDBOX_DB
        with _connect(settings.LAB_DB["MAINTENANCE_DB"]) as connection:
            exists = connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", [name]).fetchone()
            if not exists:
                try:
                    connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                except psycopg.errors.DuplicateDatabase:
                    pass  # boshqa jarayon ayni paytda yaratib bo'lgan
        _database_ready = True


def _ensure_extensions(admin):
    """Kengaytmalarni ext sxemasiga bir marta o'rnatadi (har bir jarayonda bir marta tekshiriladi)."""
    global _extensions_checked
    if _extensions_checked:
        return
    schema = sql.Identifier(EXTENSION_SCHEMA)
    with admin.transaction():
        admin.execute("SELECT pg_advisory_xact_lock(%s)", [HARDENING_LOCK_KEY])
        admin.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(schema))
        admin.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM PUBLIC").format(schema))
        admin.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO PUBLIC").format(schema))
    for extension in EXTENSIONS:
        available = admin.execute("SELECT 1 FROM pg_available_extensions WHERE name = %s", [extension]).fetchone()
        if not available:
            logger.warning("Laboratoriya serverida %s kengaytmasi yo'q: unga oid laboratoriyalar ishlamaydi.", extension)
            continue
        try:
            with admin.transaction():
                admin.execute(
                    sql.SQL("CREATE EXTENSION IF NOT EXISTS {} SCHEMA {}").format(sql.Identifier(extension), schema)
                )
        except psycopg.errors.UniqueViolation:
            pass  # boshqa jarayon ayni paytda o'rnatgan
    _extensions_checked = True


def available_extensions():
    """Qum qutida o'rnatilgan kengaytmalar (laboratoriya yaratishda tekshirish uchun)."""
    _ensure_database()
    with _connect(settings.LAB_SANDBOX_DB) as admin:
        _ensure_extensions(admin)
        return {row[0] for row in admin.execute("SELECT extname FROM pg_extension").fetchall()}


def _harden_if_needed(admin):
    """Himoya sozlamalari joyida ekanini tekshiradi (server qayta ishga tushgan bo'lsa, qayta qo'llaydi)."""
    hardened = admin.execute(
        "SELECT NOT has_table_privilege('public', 'pg_catalog.pg_database', 'SELECT') "
        "AND NOT has_schema_privilege('public', 'public', 'CREATE')"
    ).fetchone()[0]
    if not hardened:
        _harden(admin, settings.LAB_SANDBOX_DB)


def _harden(connection, sandbox_name):
    """Qum quti bazasi va serverdagi boshqa bazalardan ortiqcha umumiy huquqlarni olib tashlaydi."""
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(%s)", [HARDENING_LOCK_KEY])
        # Bir martalik rollar umumiy sxemaga hech narsa yoza olmasligi kerak
        connection.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        for view in HIDDEN_CATALOG_VIEWS:
            connection.execute(
                sql.SQL("REVOKE ALL ON {} FROM PUBLIC").format(sql.Identifier("pg_catalog", view))
            )
        # Standart holatda istalgan rol serverdagi har qanday bazaga ulana oladi; faqat
        # qum quti bazasi ochiq qoladi (platformaning asosiy bazasi ham yopiladi)
        others = connection.execute(
            "SELECT datname FROM pg_database WHERE datname <> %s AND datallowconn", [sandbox_name]
        ).fetchall()
        for (database,) in others:
            connection.execute(
                sql.SQL("REVOKE CONNECT, TEMPORARY ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database))
            )


def _drop_role(admin, role):
    identifier = sql.Identifier(role)
    admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = %s", [role])
    admin.execute(sql.SQL("DROP OWNED BY {} CASCADE").format(identifier))
    admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(identifier))


def _drop_stale_roles(admin):
    """Avariya bilan tugagan ishga tushirishlardan qolgan rollarni tozalaydi."""
    stale = admin.execute(
        "SELECT rolname FROM pg_roles WHERE rolname LIKE %s AND rolvaliduntil < now() - interval '2 minutes'",
        [ROLE_PREFIX.replace("_", r"\_") + "%"],
    ).fetchall()
    for (role,) in stale:
        try:
            _drop_role(admin, role)
        except psycopg.Error:
            logger.warning("Eskirgan laboratoriya rolini o'chirib bo'lmadi: %s", role)


def _decode(value):
    if value is None:
        return None
    text = value.decode("utf-8", "replace")
    return text if len(text) <= MAX_CELL_LENGTH else text[:MAX_CELL_LENGTH] + "…"


def _error_from_result(result, script):
    def diag(field_code):
        value = result.error_field(field_code)
        return value.decode("utf-8", "replace") if value else ""

    position = diag(pq.DiagnosticField.STATEMENT_POSITION)
    line = None
    if position.isdigit():
        line = script[: int(position) - 1].count("\n") + 1
    return SqlError(
        message=diag(pq.DiagnosticField.MESSAGE_PRIMARY) or "Noma'lum xato",
        sqlstate=diag(pq.DiagnosticField.SQLSTATE),
        detail=diag(pq.DiagnosticField.MESSAGE_DETAIL),
        hint=diag(pq.DiagnosticField.MESSAGE_HINT),
        line=line,
    )


def _storage_used(admin):
    """Qum quti bazasi fayllari (commit qilinmagan ma'lumot ham) va vaqtinchalik fayllar hajmi, baytda."""
    return admin.execute(
        "SELECT pg_database_size(current_database())"
        " + coalesce((SELECT sum(size) FROM pg_ls_tmpdir()), 0)"
    ).fetchone()[0]


def _storage_used_now():
    with _connect(settings.LAB_SANDBOX_DB) as admin:
        return _storage_used(admin)


def _execute_script(runner, script, admin=None):
    """Bir nechta buyruqdan iborat skriptni bajaradi. Qaytaradi: (xato, oxirgi natija, holat).

    Natija qatorma-qator qabul qilinadi, shuning uchun juda katta natija
    server xotirasini to'ldirib qo'ymaydi. `admin` berilsa, disk hajmi ham kuzatiladi.
    """
    pgconn = runner.pgconn
    deadline = time.monotonic() + SCRIPT_TIMEOUT_SECONDS
    timed_out = False
    cancelled = False
    too_much_data = False
    next_storage_check = time.monotonic() + STORAGE_CHECK_SECONDS

    def check_storage():
        nonlocal too_much_data, next_storage_check
        if admin is None or cancelled or time.monotonic() < next_storage_check:
            return
        next_storage_check = time.monotonic() + STORAGE_CHECK_SECONDS
        try:
            if _storage_used(admin) > MAX_STORAGE_BYTES:
                too_much_data = True
                cancel()
        except psycopg.Error:
            logger.warning("Qum quti hajmini tekshirib bo'lmadi", exc_info=True)

    def cancel():
        nonlocal cancelled, deadline
        cancelled = True
        # Bekor qilish xabari kelishi uchun yana biroz kutiladi
        deadline = time.monotonic() + 3
        try:
            pgconn.get_cancel().cancel()
        except Exception:  # ulanish allaqachon yopilgan bo'lishi mumkin
            pass

    def next_result():
        """Keyingi natijani kutadi; vaqt tugasa buyruqni bekor qiladi."""
        nonlocal timed_out
        while pgconn.is_busy():
            check_storage()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if cancelled:
                    # Bekor qilishga ham javob yo'q: ulanish uziladi
                    runner.close()
                    return None
                timed_out = True
                cancel()
                continue
            select.select([pgconn.socket], [], [], min(remaining, STORAGE_CHECK_SECONDS))
            pgconn.consume_input()
        return pgconn.get_result()

    error = None
    last_result = None
    current = None
    status_message = ""
    received = 0
    too_many_rows = False

    try:
        pgconn.send_query(script.encode("utf-8"))
        pgconn.set_single_row_mode()
        while (result := next_result()) is not None:
            check_storage()
            status = result.status
            if status in (pq.ExecStatus.SINGLE_TUPLE, pq.ExecStatus.TUPLES_OK):
                if current is None:
                    current = RowSet(
                        columns=[result.fname(index).decode("utf-8", "replace") for index in range(result.nfields)]
                    )
                if status == pq.ExecStatus.SINGLE_TUPLE:
                    received += 1
                    current.row_count += 1
                    if len(current.rows) < MAX_KEPT_ROWS:
                        current.rows.append(
                            tuple(_decode(result.get_value(0, column)) for column in range(result.nfields))
                        )
                    if received > MAX_RECEIVED_ROWS and not too_many_rows:
                        too_many_rows = True
                        cancel()
                else:
                    # Natija to'plami tugadi
                    last_result = current
                    current = None
                    status_message = (result.command_status or b"").decode("utf-8", "replace")
            elif status == pq.ExecStatus.COMMAND_OK:
                status_message = (result.command_status or b"").decode("utf-8", "replace")
            elif status == pq.ExecStatus.FATAL_ERROR:
                error = _error_from_result(result, script)
            elif status in (pq.ExecStatus.COPY_IN, pq.ExecStatus.COPY_OUT, pq.ExecStatus.COPY_BOTH):
                # COPY ... FROM STDIN / TO STDOUT ma'lumot oqimini kutadi; bu yerda ishlatilmaydi
                error = SqlError(
                    message="COPY ... FROM STDIN yoki TO STDOUT buyrug'i laboratoriyada ishlamaydi.",
                    hint="Ma'lumot qo'shish uchun INSERT dan foydalaning.",
                )
                runner.close()
                break
    except (psycopg.Error, OSError) as exc:
        error = error or SqlError(message=f"Ulanish uzildi: {exc}")

    if too_much_data:
        error = SqlError(
            message=f"Kod juda ko'p ma'lumot yozdi ({MAX_STORAGE_BYTES // (1024 * 1024)} MB dan ortiq) va to'xtatildi.",
            hint="Laboratoriya uchun kichik ma'lumot yetarli: generate_series va INSERT dagi qatorlar sonini kamaytiring.",
        )
    elif too_many_rows:
        error = SqlError(
            message=f"So'rov juda ko'p qator qaytardi ({MAX_RECEIVED_ROWS} tadan ortiq), shuning uchun to'xtatildi.",
            hint="WHERE sharti yoki LIMIT qo'shing; JOIN shartini tekshiring.",
        )
    elif timed_out:
        error = SqlError(
            message=f"Kod {SCRIPT_TIMEOUT_SECONDS} soniyadan uzoq ishladi va to'xtatildi.",
            sqlstate="57014",
        )
    return error, last_result, status_message


def _read_tables(admin, schema):
    """Skriptdan keyin sxemada qolgan jadvallar tuzilishi va ma'lumotlari."""
    tables = {}
    column_rows = admin.execute(
        """
        SELECT c.relname, a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid
        WHERE n.nspname = %s AND c.relkind IN ('r', 'p') AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY c.relname, a.attnum
        """,
        [schema],
    ).fetchall()
    # Sxema nomi har safar boshqacha, shuning uchun u matnlardan olib tashlanadi
    prefix = f"{schema}."
    for table, column, column_type, not_null in column_rows:
        state = tables.setdefault(table, TableState(columns={}, constraints=[], rows=[]))
        state.columns[column] = (column_type.replace(prefix, ""), not_null)

    constraint_rows = admin.execute(
        """
        SELECT c.relname, pg_get_constraintdef(con.oid)
        FROM pg_constraint con
        JOIN pg_class c ON c.oid = con.conrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND con.contype IN ('p', 'u', 'f', 'c')
        """,
        [schema],
    ).fetchall()
    for table, definition in constraint_rows:
        if table in tables:
            tables[table].constraints.append(definition.replace(prefix, ""))

    for table, state in tables.items():
        state.constraints.sort()
        # Ustunlar nomi bo'yicha tartiblanadi: ustunlar tartibi boshqacha bo'lsa ham ma'lumot solishtiriladi
        row_expression = sql.SQL("ROW({})::text").format(
            sql.SQL(", ").join(sql.Identifier(column) for column in sorted(state.columns))
        )
        query = sql.SQL("SELECT {} FROM {}.{} LIMIT {}").format(
            row_expression, sql.Identifier(schema), sql.Identifier(table), sql.Literal(MAX_KEPT_ROWS + 1)
        )
        rows = [row[0] for row in admin.execute(query).fetchall()]
        state.rows_truncated = len(rows) > MAX_KEPT_ROWS
        state.rows = sorted(rows[:MAX_KEPT_ROWS])
    return tables


def _plan_nodes(node):
    nodes = [PlanNode(node.get("Node Type", ""), node.get("Relation Name", ""), node.get("Index Name", ""))]
    for child in node.get("Plans", []):
        nodes += _plan_nodes(child)
    return nodes


def _explain(runner, query, outcome):
    """So'rov rejasini talaba sessiyasida (uning cheklangan roli bilan) oladi.

    Admin ulanishida emas: rejalashtirish paytida IMMUTABLE funksiyalar bajarilishi mumkin, talaba esa o'z
    funksiyasini view orqali qo'yib qo'yishi mumkin. RESET ALL — talaba SET enable_seqscan = off kabi
    sozlamalar bilan rejani "aldamasligi" uchun (ulanish parametrlari, masalan search_path, saqlanib qoladi).
    """
    if runner.closed:
        outcome.plan_error = SqlError(message="So'rov rejasini olib bo'lmadi: ulanish uzilgan.")
        return
    try:
        runner.execute("RESET ALL")
        document = runner.execute(f"EXPLAIN (FORMAT JSON) {query}").fetchone()[0]
        outcome.plan_nodes = _plan_nodes(document[0]["Plan"])
        outcome.plan_cost = float(document[0]["Plan"]["Total Cost"])
        outcome.plan = [row[0] for row in runner.execute(f"EXPLAIN (COSTS OFF) {query}").fetchall()]
    except psycopg.Error as exc:
        diag = exc.diag
        outcome.plan_error = SqlError(
            message=(diag.message_primary if diag else None) or str(exc).splitlines()[0],
            sqlstate=(diag.sqlstate if diag else None) or "",
        )


def _create_role(admin, connection_limit=1):
    """Bir martalik rol va uning sxemasi. Qaytaradi: (rol nomi, parol). Keyin _drop_role bilan o'chiriladi."""
    role = ROLE_PREFIX + uuid.uuid4().hex[:20]
    password = secrets.token_hex(24)
    identifier = sql.Identifier(role)
    admin.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
    _harden_if_needed(admin)
    _ensure_extensions(admin)
    _drop_stale_roles(admin)
    # Parol bir daqiqadan keyin o'z kuchini yo'qotadi
    valid_until = admin.execute("SELECT (now() + interval '1 minute')::text").fetchone()[0]
    admin.execute(
        sql.SQL(
            "CREATE ROLE {} LOGIN PASSWORD {} CONNECTION LIMIT {} "
            "NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT VALID UNTIL {}"
        ).format(identifier, sql.Literal(password), sql.Literal(connection_limit), sql.Literal(valid_until))
    )
    admin.execute(sql.SQL("ALTER ROLE {} SET temp_file_limit = {}").format(identifier, sql.Literal(TEMP_FILE_LIMIT)))
    try:
        admin.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(identifier, identifier))
    except psycopg.Error:
        _drop_role(admin, role)
        raise
    return role, password


def _connect_runner(role, password, extra_options=""):
    return _connect(
        settings.LAB_SANDBOX_DB,
        user=role,
        password=password,
        # ext — kengaytmalar turlari va operatorlari (masalan, vector va <->); talaba sxemasi birinchi turadi
        options=f"-c search_path={role},{EXTENSION_SCHEMA} -c statement_timeout={STATEMENT_TIMEOUT_MS} {extra_options}".strip(),
    )


def run_sql(script, setup_sql="", explain_sql=""):
    """`setup_sql` dan keyin `script` ni toza sxemada bajaradi va natijani qaytaradi.

    `explain_sql` berilsa, skriptdan keyin shu so'rovning rejasi ham olinadi (so'rovning o'zi bajarilmaydi).
    """
    _ensure_database()
    outcome = RunOutcome()

    with _connect(settings.LAB_SANDBOX_DB) as admin:
        role, password = _create_role(admin)
        try:
            runner = _connect_runner(role, password)
            try:
                if setup_sql.strip():
                    setup_error, _, _ = _execute_script(runner, setup_sql, admin)
                    if setup_error:
                        outcome.error = setup_error
                        outcome.setup_failed = True
                        return outcome
                outcome.error, outcome.result, outcome.status_message = _execute_script(runner, script, admin)
                if explain_sql.strip() and outcome.error is None:
                    _explain(runner, explain_sql, outcome)
            finally:
                runner.close()
            if outcome.error is None:
                outcome.tables = _read_tables(admin, role)
        finally:
            try:
                _drop_role(admin, role)
            except psycopg.Error:
                logger.exception("Laboratoriya rolini o'chirib bo'lmadi: %s", role)
    return outcome


# Barcha sinovlar uchun umumiy vaqt: talaba trigger'i har bir sinovni sekinlashtirsa ham tekshiruv cho'zilmaydi
PROBES_TIME_BUDGET_SECONDS = 20
PROBE_TIMEOUT_ERROR = SqlError("Sinovlar uchun ajratilgan vaqt tugadi.", sqlstate="57014")


def run_probes(script, setup_sql, probes):
    """`setup_sql` va `script` dan keyin har bir sinov buyrug'ini alohida tranzaksiyada bajarib, orqaga qaytaradi:
    sinovlar bir-biriga ta'sir qilmaydi.

    Qaytaradi: (RunOutcome — talaba kodi natijasi, [SqlError | None] — har bir sinov xatosi; None — bajarildi).
    Talaba kodi xato bersa, sinovlar bajarilmaydi (ro'yxat bo'sh).
    """
    outcome, results = run_followups(script, setup_sql, probes)
    return outcome, [error for error, _ in results]


def run_followups(script, setup_sql, followups):
    """run_probes kabi, lekin har bir buyruq uchun (xato, oxirgi natija) qaytaradi: migratsiyadan keyingi so'rovlar
    natijasini solishtirish uchun (labs/evolution.py)."""
    _ensure_database()
    outcome, errors = RunOutcome(), []

    with _connect(settings.LAB_SANDBOX_DB) as admin:
        role, password = _create_role(admin)
        try:
            runner = _connect_runner(role, password)
            try:
                if setup_sql.strip():
                    setup_error, _, _ = _execute_script(runner, setup_sql, admin)
                    if setup_error:
                        outcome.error = setup_error
                        outcome.setup_failed = True
                        return outcome, errors
                outcome.error, outcome.result, outcome.status_message = _execute_script(runner, script, admin)
                if outcome.error is None:
                    deadline = time.monotonic() + PROBES_TIME_BUDGET_SECONDS
                    for sql in followups:
                        if runner.closed or time.monotonic() > deadline:
                            errors.append((PROBE_TIMEOUT_ERROR, None))
                            continue
                        error, result, _ = _execute_script(runner, f"BEGIN;\n{sql}\n;", admin)
                        errors.append((error, result))
                        if not runner.closed:
                            # Xato bo'lsa tranzaksiya ochiq qoladi; muvaffaqiyatli bo'lsa o'zgarish bekor qilinadi
                            _execute_script(runner, "ROLLBACK", admin)
            finally:
                runner.close()
            if outcome.error is None:
                outcome.tables = _read_tables(admin, role)
        finally:
            try:
                _drop_role(admin, role)
            except psycopg.Error:
                logger.exception("Laboratoriya rolini o'chirib bo'lmadi: %s", role)
    return outcome, errors


# ---------- Ikki sessiya bir vaqtda (tranzaksiyalar laboratoriyasi) ----------

MAX_CONCURRENT_STATEMENTS = 20
# Shuncha vaqt ichida javob kelmasa, sessiya qulf kutyapti deb hisoblanadi va ikkinchisi davom etadi
BLOCK_DETECT_SECONDS = 0.3
CONCURRENT_TIMEOUT_SECONDS = 12
# Cheksiz kutish bo'lmasin; o'zaro qulflanishni (deadlock) PostgreSQL o'zi ~1 soniyada aniqlaydi
LOCK_TIMEOUT_MS = 4000
STEP_SHOWN_ROWS = 5
MAX_STEP_SQL_LENGTH = 300


def split_statements(script):
    """Skriptni alohida buyruqlarga ajratadi: matn ('...'), nomlar ("..."), $teg$...$teg$ bloklari va
    izohlar ichidagi nuqtali vergul hisobga olinmaydi."""
    statements, current, index, length = [], [], 0, len(script)
    while index < length:
        char = script[index]
        if char in ("'", '"'):
            end = index + 1
            while end < length:
                if script[end] == char:
                    if end + 1 < length and script[end + 1] == char:
                        end += 2
                        continue
                    break
                end += 1
            current.append(script[index : end + 1])
            index = end + 1
        elif script.startswith("--", index):
            end = script.find("\n", index)
            index = length if end == -1 else end
        elif script.startswith("/*", index):
            end = script.find("*/", index + 2)
            index = length if end == -1 else end + 2
        elif char == "$" and (match := re.match(r"\$[A-Za-z_]*\$", script[index:])):
            tag = match.group(0)
            end = script.find(tag, index + len(tag))
            end = length if end == -1 else end + len(tag)
            current.append(script[index:end])
            index = end
        elif char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            index += 1
        else:
            current.append(char)
            index += 1
    statement = "".join(current).strip()
    if statement:
        statements.append(statement)
    return statements


@dataclass
class ConcurrentStep:
    """Vaqt chizig'idagi bitta voqea: sessiya buyruqni boshladi, qulf kutdi yoki tugatdi."""

    session: str
    sql: str
    # ok — bajarildi; waiting — qulf kutmoqda; resumed — kutishdan keyin bajarildi; error — xato
    status: str
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    message: str = ""


@dataclass
class ConcurrentOutcome:
    error: SqlError | None = None
    # Xato bergan sessiya ("A" yoki "B")
    error_session: str = ""
    setup_failed: bool = False
    steps: list[ConcurrentStep] = field(default_factory=list)
    tables: dict[str, TableState] = field(default_factory=dict)


class _Session:
    def __init__(self, name, connection, statements):
        self.name = name
        self.connection = connection
        self.pgconn = connection.pgconn
        self.statements = statements
        self.next = 0
        self.running = None  # bajarilayotgan buyruq raqami
        self.started_at = 0.0
        self.waiting = False
        self.failed = False
        self.columns, self.rows, self.received = [], [], 0
        self.error = None

    @property
    def done(self):
        return self.failed or (self.next >= len(self.statements) and self.running is None)

    def start(self, index):
        self.running, self.started_at, self.waiting = index, time.monotonic(), False
        self.columns, self.rows, self.received, self.error = [], [], 0, None
        self.pgconn.send_query(self.statements[index].encode("utf-8"))
        self.pgconn.set_single_row_mode()

    def drain(self):
        """Kelgan natijalarni o'qiydi. Qaytaradi: buyruq tugadimi."""
        self.pgconn.consume_input()
        while not self.pgconn.is_busy():
            result = self.pgconn.get_result()
            if result is None:
                return True
            status = result.status
            if status in (pq.ExecStatus.SINGLE_TUPLE, pq.ExecStatus.TUPLES_OK):
                if not self.columns:
                    self.columns = [result.fname(i).decode("utf-8", "replace") for i in range(result.nfields)]
                if status == pq.ExecStatus.SINGLE_TUPLE:
                    self.received += 1
                    if len(self.rows) < STEP_SHOWN_ROWS:
                        self.rows.append(tuple(_decode(result.get_value(0, i)) for i in range(result.nfields)))
                    if self.received > MAX_RECEIVED_ROWS:
                        self.error = SqlError(message=f"So'rov {MAX_RECEIVED_ROWS} tadan ortiq qator qaytardi.")
                        self.pgconn.get_cancel().cancel()
            elif status == pq.ExecStatus.FATAL_ERROR:
                self.error = self.error or _error_from_result(result, self.statements[self.running])
            elif status in (pq.ExecStatus.COPY_IN, pq.ExecStatus.COPY_OUT, pq.ExecStatus.COPY_BOTH):
                self.error = SqlError(message="COPY buyrug'i laboratoriyada ishlamaydi.")
                self.connection.close()
                return True
        return False


def run_concurrent(script, setup_sql=""):
    """`setup_sql` dan keyin `script` ni ikki sessiyada (A va B) bir vaqtda bajaradi.

    Tartib — eng xavflisi: A ning COMMIT gacha bo'lgan buyruqlari, keyin B ning, keyin A COMMIT, B COMMIT.
    Sessiya qulf kutib qolsa (BLOCK_DETECT_SECONDS ichida javob yo'q), ikkinchisi davom etadi.
    """
    _ensure_database()
    outcome = ConcurrentOutcome()
    statements = split_statements(script)
    if not statements or len(statements) > MAX_CONCURRENT_STATEMENTS:
        outcome.error = SqlError(message=f"Kodda 1 tadan {MAX_CONCURRENT_STATEMENTS} tagacha buyruq bo'lishi kerak.")
        return outcome
    body = len(statements) - 1
    order = [("A", i) for i in range(body)] + [("B", i) for i in range(body)] + [("A", body), ("B", body)]

    with _connect(settings.LAB_SANDBOX_DB) as admin:
        role, password = _create_role(admin, connection_limit=2)
        sessions = {}
        try:
            options = f"-c lock_timeout={LOCK_TIMEOUT_MS}"
            first = _connect_runner(role, password, options)
            sessions["A"] = _Session("A", first, statements)
            if setup_sql.strip():
                setup_error, _, _ = _execute_script(first, setup_sql, admin)
                if setup_error:
                    outcome.error, outcome.setup_failed = setup_error, True
                    return outcome
            sessions["B"] = _Session("B", _connect_runner(role, password, options), statements)
            _schedule(sessions, order, outcome, admin)
        finally:
            for session in sessions.values():
                session.connection.close()  # COMMIT qilinmagan o'zgarishlar bekor bo'ladi
            try:
                if outcome.error is None:
                    outcome.tables = _read_tables(admin, role)
            finally:
                try:
                    _drop_role(admin, role)
                except psycopg.Error:
                    logger.exception("Laboratoriya rolini o'chirib bo'lmadi: %s", role)
    return outcome


def _schedule(sessions, order, outcome, admin):
    deadline = time.monotonic() + CONCURRENT_TIMEOUT_SECONDS
    next_storage_check = 0.0
    pending = list(order)

    def short(text):
        text = " ".join(text.split())
        return text if len(text) <= MAX_STEP_SQL_LENGTH else text[:MAX_STEP_SQL_LENGTH] + "…"

    def finish(session):
        index, waited = session.running, session.waiting
        session.running = None
        session.next = index + 1
        if session.error:
            session.failed = True
            outcome.steps.append(ConcurrentStep(session.name, short(session.statements[index]), "error", message=session.error.message))
            if outcome.error is None:
                outcome.error, outcome.error_session = session.error, session.name
        else:
            outcome.steps.append(
                ConcurrentStep(
                    session.name,
                    short(session.statements[index]),
                    "resumed" if waited else "ok",
                    session.columns,
                    session.rows,
                )
            )

    while True:
        # Navbatdagi buyruqni boshlash: faqat hech kim bajarmayotgan bo'lsa yoki bajarayotgani qulf kutsa
        pending = [item for item in pending if not sessions[item[0]].failed]
        running = [s for s in sessions.values() if s.running is not None]
        if all(s.waiting for s in running):
            for item in pending:
                session = sessions[item[0]]
                if session.running is None and session.next == item[1]:
                    pending.remove(item)
                    session.start(item[1])
                    break
        running = [s for s in sessions.values() if s.running is not None]
        if not running:
            # Hamma buyruq bajarildi (yoki boshlab bo'lmaydi — bu bo'lmasligi kerak, lekin cheksiz sikl ham bo'lmasin)
            return

        if time.monotonic() > deadline:
            for session in running:
                session.pgconn.get_cancel().cancel()
            outcome.error = outcome.error or SqlError(
                message=f"Kod {CONCURRENT_TIMEOUT_SECONDS} soniyadan uzoq ishladi va to'xtatildi.", sqlstate="57014"
            )
            for session in sessions.values():
                session.failed = True
            return

        if time.monotonic() >= next_storage_check:
            next_storage_check = time.monotonic() + STORAGE_CHECK_SECONDS
            if _storage_used(admin) > MAX_STORAGE_BYTES:
                for session in running:
                    session.pgconn.get_cancel().cancel()
                outcome.error = SqlError(message=f"Kod juda ko'p ma'lumot yozdi ({MAX_STORAGE_BYTES // (1024 * 1024)} MB dan ortiq).")
                for session in sessions.values():
                    session.failed = True
                return

        select.select([s.pgconn.socket for s in running], [], [], 0.05)
        for session in running:
            if session.drain():
                finish(session)
            elif not session.waiting and time.monotonic() - session.started_at >= BLOCK_DETECT_SECONDS:
                session.waiting = True
                outcome.steps.append(ConcurrentStep(session.name, short(session.statements[session.running]), "waiting"))
