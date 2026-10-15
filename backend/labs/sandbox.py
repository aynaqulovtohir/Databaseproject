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

_database_ready = False
_database_lock = threading.Lock()


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


def _execute_script(runner, script):
    """Bir nechta buyruqdan iborat skriptni bajaradi. Qaytaradi: (xato, oxirgi natija, holat).

    Natija qatorma-qator qabul qilinadi, shuning uchun juda katta natija
    server xotirasini to'ldirib qo'ymaydi.
    """
    pgconn = runner.pgconn
    deadline = time.monotonic() + SCRIPT_TIMEOUT_SECONDS
    timed_out = False
    cancelled = False

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
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if cancelled:
                    # Bekor qilishga ham javob yo'q: ulanish uziladi
                    runner.close()
                    return None
                timed_out = True
                cancel()
                continue
            select.select([pgconn.socket], [], [], min(remaining, 1.0))
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

    if too_many_rows:
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


def run_sql(script, setup_sql=""):
    """`setup_sql` dan keyin `script` ni toza sxemada bajaradi va natijani qaytaradi."""
    _ensure_database()
    role = ROLE_PREFIX + uuid.uuid4().hex[:20]
    password = secrets.token_hex(24)
    identifier = sql.Identifier(role)
    outcome = RunOutcome()

    with _connect(settings.LAB_SANDBOX_DB) as admin:
        admin.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
        _harden_if_needed(admin)
        _drop_stale_roles(admin)
        # Parol bir daqiqadan keyin o'z kuchini yo'qotadi
        valid_until = admin.execute("SELECT (now() + interval '1 minute')::text").fetchone()[0]
        admin.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN PASSWORD {} CONNECTION LIMIT 1 "
                "NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT VALID UNTIL {}"
            ).format(identifier, sql.Literal(password), sql.Literal(valid_until))
        )
        admin.execute(
            sql.SQL("ALTER ROLE {} SET temp_file_limit = {}").format(identifier, sql.Literal(TEMP_FILE_LIMIT))
        )
        try:
            admin.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(identifier, identifier))
            runner = _connect(
                settings.LAB_SANDBOX_DB,
                user=role,
                password=password,
                options=f"-c search_path={role} -c statement_timeout={STATEMENT_TIMEOUT_MS}",
            )
            try:
                if setup_sql.strip():
                    setup_error, _, _ = _execute_script(runner, setup_sql)
                    if setup_error:
                        outcome.error = setup_error
                        outcome.setup_failed = True
                        return outcome
                outcome.error, outcome.result, outcome.status_message = _execute_script(runner, script)
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
