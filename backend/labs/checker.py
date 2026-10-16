"""Talaba kodini ishga tushirib, namunaviy yechim bilan solishtiradi va xatoni tushuntiradi."""
import re
from collections import Counter

from .sandbox import SqlError, run_sql

MAX_DISPLAY_ROWS = 100
MAX_DIFFERENCES = 8

# Eng ko'p uchraydigan PostgreSQL xatolari uchun o'zbekcha tushuntirish (SQLSTATE bo'yicha)
ERROR_TIPS = {
    "42601": "Sintaksis xatosi. Ko'rsatilgan so'z atrofini tekshiring: kalit so'z noto'g'ri yozilgan, "
    "vergul, qavs yoki nuqtali vergul tushib qolgan bo'lishi mumkin.",
    "42P01": "Bunday jadval topilmadi. Jadval nomi to'g'ri yozilganini va u shu koddan oldin "
    "yaratilganini tekshiring.",
    "42703": "Bunday ustun topilmadi. Ustun nomini va u qaysi jadvalga tegishli ekanini tekshiring. "
    "Matn qiymatlari qo'shtirnoqda emas, bitta tirnoqda ('...') yoziladi.",
    "42P07": "Bunday nomli jadval allaqachon mavjud. Boshqa nom tanlang yoki jadvalni ikki marta yaratmang.",
    "42701": "Bitta jadvalda bir xil nomli ustun ikki marta yozilgan.",
    "42702": "Bu ustun nomi bir nechta jadvalda bor. Qaysi jadvalniki ekanini ko'rsating: jadval.ustun.",
    "42803": "SELECT dagi agregat funksiya (COUNT, SUM, ...) ichida bo'lmagan har bir ustun "
    "GROUP BY da ham yozilishi kerak.",
    "42883": "Bunday funksiya yoki operator yo'q. Funksiya nomini va argumentlar turini tekshiring "
    "(masalan, matn bilan sonni to'g'ridan-to'g'ri solishtirib bo'lmaydi).",
    "42804": "Ma'lumot turlari mos emas. Ustun turi va unga berilayotgan qiymat turini tekshiring.",
    "42704": "Bunday ma'lumot turi yoki obyekt yo'q. Tur nomi to'g'ri yozilganini tekshiring.",
    "42830": "Tashqi kalit bog'lanayotgan ustun PRIMARY KEY yoki UNIQUE bo'lishi kerak.",
    "42P16": "Jadval ta'rifi noto'g'ri: masalan, bitta jadvalda ikkita PRIMARY KEY bo'lishi mumkin emas.",
    "42501": "Bu amalga ruxsat yo'q. Laboratoriyada faqat o'z jadvallaringiz bilan ishlashingiz mumkin; "
    "jadval nomi oldiga sxema nomi (masalan, public.) yozmang.",
    "22P02": "Qiymat ustun turiga to'g'ri kelmaydi (masalan, son ustuniga matn yozilgan).",
    "22001": "Matn ustun uchun belgilangan uzunlikdan (VARCHAR(n)) oshib ketdi.",
    "22003": "Son ustun turi sig'dira oladigan chegaradan chiqib ketdi.",
    "22012": "Nolga bo'lish. Bo'luvchi nol bo'lmasligini tekshiring (NULLIF yordam beradi).",
    "21000": "Ichki so'rov bitta qiymat o'rniga bir nechta qator qaytardi. "
    "= o'rniga IN ishlating yoki ichki so'rovni toraytiring.",
    "23502": "NOT NULL ustunga qiymat berilmagan. INSERT da shu ustunni ham to'ldiring.",
    "23503": "Tashqi kalit buzildi: bog'langan jadvalda bunday qiymat yo'q "
    "(yoki o'chirilayotgan qatorga boshqa jadval bog'langan).",
    "23505": "UNIQUE yoki PRIMARY KEY buzildi: bunday qiymat jadvalda allaqachon bor.",
    "23514": "CHECK cheklovi buzildi: qiymat ustunga qo'yilgan shartga to'g'ri kelmaydi.",
    "57014": "Kod juda uzoq ishladi. Cheksiz sikl yoki shartsiz JOIN (juda ko'p qator) yo'qligini tekshiring.",
}

CONSTRAINT_KINDS = ("PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK")


class LabSetupError(Exception):
    """Laboratoriyaning o'zida (boshlang'ich jadvallar yoki namunaviy yechim) xato bor."""

    def __init__(self, field, error):
        self.field = field
        self.error = error
        super().__init__(format_error(error))


def format_error(error):
    text = error.message
    if error.line:
        text = f"{error.line}-qator: {text}"
    if error.detail:
        text = f"{text} ({error.detail})"
    return text


def _error_payload(error):
    return {
        "message": error.message,
        # Tadqiqot eksportida xato turini aniqlash uchun saqlanadi
        "sqlstate": error.sqlstate,
        "detail": error.detail,
        "hint": error.hint,
        "line": error.line,
        "tip": ERROR_TIPS.get(error.sqlstate, ""),
    }


def _result_payload(result):
    if result is None:
        return None
    return {
        "columns": result.columns,
        "rows": [list(row) for row in result.rows[:MAX_DISPLAY_ROWS]],
        "row_count": result.row_count,
        "truncated": result.row_count > MAX_DISPLAY_ROWS,
    }


def _compare_results(student, expected, ordered):
    """So'rov natijalarini solishtiradi. Ustun nomlari hisobga olinmaydi."""
    if expected is None:
        return []
    if student is None:
        return ["Kod natija qaytarmadi: oxirgi buyruq natija chiqaradigan so'rov (SELECT) bo'lishi kerak."]
    if len(student.columns) != len(expected.columns):
        return [
            f"Natijadagi ustunlar soni farq qiladi: sizda {len(student.columns)} ta, "
            f"kutilgan {len(expected.columns)} ta."
        ]
    if student.row_count != expected.row_count:
        return [
            f"Natijadagi qatorlar soni farq qiladi: sizda {student.row_count} ta, "
            f"kutilgan {expected.row_count} ta."
        ]
    if student.rows == expected.rows:
        return []
    if Counter(student.rows) != Counter(expected.rows):
        return ["Qatorlar soni to'g'ri, lekin ayrim qiymatlar kutilganidan farq qiladi."]
    if ordered:
        return ["Qatorlar to'g'ri, lekin tartibi kutilganidan farq qiladi (ORDER BY ni tekshiring)."]
    return []


def _constraint_kind(definition):
    return next((kind for kind in CONSTRAINT_KINDS if definition.startswith(kind)), "cheklov")


def _compare_tables(student, expected):
    """Koddan keyingi jadvallar holatini solishtiradi: tuzilish, cheklovlar va ma'lumotlar."""
    differences = []
    for table in sorted(expected.keys() - student.keys()):
        differences.append(f"«{table}» jadvali yo'q (yaratilmagan yoki o'chirib yuborilgan).")
    for table in sorted(student.keys() - expected.keys()):
        differences.append(f"Ortiqcha jadval: «{table}».")

    for table in sorted(expected.keys() & student.keys()):
        mine, wanted = student[table], expected[table]
        missing_columns = sorted(wanted.columns.keys() - mine.columns.keys())
        extra_columns = sorted(mine.columns.keys() - wanted.columns.keys())
        if missing_columns:
            differences.append(f"«{table}» jadvalida ustun yetishmaydi: {', '.join(missing_columns)}.")
        if extra_columns:
            differences.append(f"«{table}» jadvalida ortiqcha ustun: {', '.join(extra_columns)}.")
        for column in sorted(wanted.columns.keys() & mine.columns.keys()):
            (my_type, my_not_null), (wanted_type, wanted_not_null) = mine.columns[column], wanted.columns[column]
            if my_type != wanted_type:
                differences.append(
                    f"«{table}.{column}» ustunining turi: sizda {my_type}, kutilgan {wanted_type}."
                )
            elif my_not_null != wanted_not_null:
                differences.append(
                    f"«{table}.{column}» ustuni NOT NULL bo'lishi kerak."
                    if wanted_not_null
                    else f"«{table}.{column}» ustuni bo'sh (NULL) qiymatga ruxsat berishi kerak."
                )

        # Talaba qo'shgan ortiqcha cheklovlar xato hisoblanmaydi
        missing_constraints = Counter(wanted.constraints) - Counter(mine.constraints)
        for kind, count in sorted(Counter(_constraint_kind(item) for item in missing_constraints.elements()).items()):
            differences.append(
                f"«{table}» jadvalida {kind} cheklovi yetishmaydi yoki kutilganidan boshqacha"
                + (f" ({count} ta)." if count > 1 else ".")
            )

        if not missing_columns and not extra_columns and mine.rows != wanted.rows:
            if len(mine.rows) == len(wanted.rows):
                differences.append(
                    f"«{table}» jadvalida qatorlar soni to'g'ri, lekin ayrim qiymatlar kutilganidan farq qiladi "
                    "(ortiqcha bo'sh joy, harf yoki raqam xatosi bo'lishi mumkin)."
                )
            else:
                differences.append(
                    f"«{table}» jadvalidagi ma'lumotlar kutilganidan farq qiladi "
                    f"(sizda {len(mine.rows)} qator, kutilgan {len(wanted.rows)} qator)."
                )
    return differences


# Yashirin ma'lumotlarda farq chiqqanda: qaysi qator yoki qiymat farq qilgani aytilmaydi (yashirin ma'lumot sir)
HIDDEN_MISMATCH = (
    "Kod ko'rinib turgan ma'lumotlarda to'g'ri natija berdi, lekin boshqa (yashirin) ma'lumotlarda natija "
    "kutilganidan farq qildi. Natijani qo'lda yozmang: so'rov istalgan ma'lumotlar uchun to'g'ri ishlashi kerak "
    "(shartlar, JOIN va guruhlashni tekshiring)."
)


# Indeks laboratoriyasida taqiqlash mumkin bo'lgan reja tugunlari va talabaga tushuntirish
PLAN_NODE_TIPS = {
    "Seq Scan": "jadval boshidan oxirigacha to'liq o'qilyapti — shartdagi ustun(lar)ga mos indeks kerak",
    "Sort": "natija alohida saralanyapti — indeks saralash tartibini ham qamrab olsin",
    "Bitmap Heap Scan": "indeks faqat qisman ishlatilyapti — shartning barcha ustunlarini qamrab oluvchi indeks kerak",
}


# Taqiqlangan tugun bo'lmasa ham, reja namunaviy yechimnikidan shuncha marta qimmat bo'lsa — indeks mos emas
# (masalan, ustunlar tartibi teskari tarkibli indeks). To'g'ri indekslar odatda ~1x, noto'g'rilari 8x dan ortiq
PLAN_COST_FACTOR = 2.0


def forbidden_nodes(lab):
    return [item.strip() for item in lab.plan_forbidden.split(",") if item.strip()]


def _plan_differences(outcome, forbidden):
    if outcome.plan_error:
        return [f"Tekshiriladigan so'rovning rejasini olib bo'lmadi: {outcome.plan_error.message}"]
    differences = []
    for node_type in forbidden:
        relations = sorted({node.relation for node in outcome.plan_nodes if node.node_type == node_type and node.relation})
        if any(node.node_type == node_type for node in outcome.plan_nodes):
            where = f" ({', '.join(relations)})" if relations else ""
            differences.append(f"So'rov rejasida hali ham «{node_type}» bor{where}: {PLAN_NODE_TIPS.get(node_type, '')}.")
    return differences


def validate_plan(setup_sql, solution_sql, plan_query, forbidden):
    """Indeks laboratoriyasi: indekssiz rejada taqiqlangan tugun bor, namunaviy yechimdan keyin esa yo'q."""
    unknown = [item for item in forbidden if item not in PLAN_NODE_TIPS]
    if unknown or not forbidden:
        raise LabSetupError(
            "plan_forbidden", SqlError(f"Ruxsat etilgan tugunlar: {', '.join(PLAN_NODE_TIPS)}.")
        )
    before = run_sql("SELECT 1", setup_sql, plan_query)
    if before.error or before.plan_error:
        raise LabSetupError("plan_query", before.error or before.plan_error)
    if not _plan_differences(before, forbidden):
        raise LabSetupError(
            "plan_query",
            SqlError("Indekssiz ham rejada taqiqlangan tugun yo'q: laboratoriya hech narsani tekshirmaydi."),
        )
    after = run_sql(solution_sql, setup_sql, plan_query)
    if after.error:
        raise LabSetupError("solution_sql", after.error)
    remaining = _plan_differences(after, forbidden)
    if remaining:
        raise LabSetupError("solution_sql", SqlError(f"Namunaviy yechimdan keyin ham: {remaining[0]}"))


def _plan_payload(outcome):
    return outcome.plan or None


def _table_columns(tables):
    return {name: set(state.columns) for name, state in tables.items()}


def validate_lab_sql(setup_sql, solution_sql, hidden_setup_sql=""):
    """Laboratoriyani saqlashdan oldin: boshlang'ich jadvallar va namunaviy yechim ishlashini tekshiradi.

    Yashirin ma'lumotlar berilgan bo'lsa: ular xatosiz ishlaydi, jadvallar tuzilishi ko'rinadigan bilan bir xil
    va namunaviy yechim ularda ham ishlaydi.
    """
    solution = solution_sql if solution_sql.strip() else "SELECT 1"
    outcome = run_sql(solution, setup_sql)
    if outcome.error:
        raise LabSetupError("setup_sql" if outcome.setup_failed else "solution_sql", outcome.error)
    if not hidden_setup_sql.strip():
        return
    if not solution_sql.strip():
        raise LabSetupError(
            "hidden_setup_sql", SqlError("Yashirin ma'lumotlar faqat namunaviy yechim bor laboratoriyada ishlatiladi.")
        )
    visible = run_sql("SELECT 1", setup_sql)
    hidden = run_sql("SELECT 1", hidden_setup_sql)
    if hidden.error:
        raise LabSetupError("hidden_setup_sql", hidden.error)
    if _table_columns(hidden.tables) != _table_columns(visible.tables):
        raise LabSetupError(
            "hidden_setup_sql",
            SqlError("Yashirin ma'lumotlar boshlang'ich jadvallar bilan bir xil jadval va ustunlarni yaratishi kerak."),
        )
    hidden_solution = run_sql(solution_sql, hidden_setup_sql)
    if hidden_solution.error:
        raise LabSetupError("solution_sql", hidden_solution.error)


def _tables_payload(tables):
    return [
        {
            "name": name,
            "columns": [
                {"name": column, "type": column_type, "not_null": not_null}
                for column, (column_type, not_null) in state.columns.items()
            ],
            "constraints": state.constraints,
            "row_count": len(state.rows),
            "rows_truncated": state.rows_truncated,
        }
        for name, state in sorted(tables.items())
    ]


def try_code(lab, sql_code):
    """Erkin sinash: kodni boshlang'ich jadvallar bilan bajaradi, lekin tekshirmaydi.

    Namunaviy yechim ishga tushirilmaydi: javobdan yechim haqida hech narsa bilib bo'lmaydi.
    """
    outcome = run_sql(sql_code, lab.setup_sql, lab.plan_query)
    if outcome.setup_failed:
        raise LabSetupError("setup_sql", outcome.error)
    return {
        "error": _error_payload(outcome.error) if outcome.error else None,
        "result": _result_payload(outcome.result),
        "status_message": outcome.status_message,
        "tables": _tables_payload(outcome.tables),
        "plan": _plan_payload(outcome),
    }


def _passes_hidden(lab, sql_code, ordered):
    """Talaba kodini yashirin ma'lumotlarda namunaviy yechim bilan solishtiradi.

    Talabaga faqat ha/yo'q qaytadi: xato matni ham yashirin qiymatlarni ochib qo'yishi mumkin (masalan,
    "Key (id)=(7) already exists"), shuning uchun u ham ko'rsatilmaydi.
    """
    student = run_sql(sql_code, lab.hidden_setup_sql)
    if student.setup_failed:
        raise LabSetupError("hidden_setup_sql", student.error)
    if student.error:
        return False
    expected = run_sql(lab.solution_sql, lab.hidden_setup_sql)
    if expected.error:
        raise LabSetupError("hidden_setup_sql" if expected.setup_failed else "solution_sql", expected.error)
    differences = _compare_results(student.result, expected.result, ordered)
    return not differences and not _compare_tables(student.tables, expected.tables)


def check_code(lab, sql_code):
    """Kodni ishga tushiradi va tekshiruv natijasini lug'at ko'rinishida qaytaradi."""
    outcome = run_sql(sql_code, lab.setup_sql, lab.plan_query)
    if outcome.setup_failed:
        raise LabSetupError("setup_sql", outcome.error)

    has_solution = bool(lab.solution_sql.strip())
    differences = []
    expected = None
    if outcome.error is None and has_solution:
        expected = run_sql(lab.solution_sql, lab.setup_sql, lab.plan_query)
        if expected.error:
            raise LabSetupError("setup_sql" if expected.setup_failed else "solution_sql", expected.error)
        ordered = bool(re.search(r"\border\s+by\b", lab.solution_sql, re.IGNORECASE))
        differences = _compare_results(outcome.result, expected.result, ordered)
        differences += _compare_tables(outcome.tables, expected.tables)
        if not differences and lab.hidden_setup_sql.strip() and not _passes_hidden(lab, sql_code, ordered):
            differences = [HIDDEN_MISMATCH]
    if outcome.error is None and lab.plan_query.strip():
        plan_differences = _plan_differences(outcome, forbidden_nodes(lab))
        if (
            not plan_differences
            and expected is not None
            and expected.plan_cost
            and outcome.plan_cost is not None
            and outcome.plan_cost > PLAN_COST_FACTOR * expected.plan_cost
        ):
            plan_differences.append(
                "Rejada taqiqlangan tugun yo'q, lekin so'rov hali ham sekin: rejalashtiruvchi baholagan narx "
                f"kutilganidan {outcome.plan_cost / expected.plan_cost:.0f} marta yuqori. Indeks so'rovdagi shartga "
                "mos kelishini tekshiring (tarkibli indeksda ustunlar tartibi muhim)."
            )
        differences += plan_differences

    return {
        "is_correct": outcome.error is None and not differences,
        "error": _error_payload(outcome.error) if outcome.error else None,
        "result": _result_payload(outcome.result),
        "status_message": outcome.status_message,
        "differences": differences[:MAX_DIFFERENCES],
        "checked_against_solution": has_solution,
        "plan": _plan_payload(outcome),
    }
