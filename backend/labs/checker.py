"""Talaba kodini ishga tushirib, namunaviy yechim bilan solishtiradi va xatoni tushuntiradi."""
import re
from collections import Counter

from .sandbox import run_sql

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


def validate_lab_sql(setup_sql, solution_sql):
    """Laboratoriyani saqlashdan oldin: boshlang'ich jadvallar va namunaviy yechim ishlashini tekshiradi."""
    outcome = run_sql(solution_sql if solution_sql.strip() else "SELECT 1", setup_sql)
    if outcome.error:
        raise LabSetupError("setup_sql" if outcome.setup_failed else "solution_sql", outcome.error)


def check_code(lab, sql_code):
    """Kodni ishga tushiradi va tekshiruv natijasini lug'at ko'rinishida qaytaradi."""
    outcome = run_sql(sql_code, lab.setup_sql)
    if outcome.setup_failed:
        raise LabSetupError("setup_sql", outcome.error)

    has_solution = bool(lab.solution_sql.strip())
    differences = []
    if outcome.error is None and has_solution:
        expected = run_sql(lab.solution_sql, lab.setup_sql)
        if expected.error:
            raise LabSetupError("setup_sql" if expected.setup_failed else "solution_sql", expected.error)
        ordered = bool(re.search(r"\border\s+by\b", lab.solution_sql, re.IGNORECASE))
        differences = _compare_results(outcome.result, expected.result, ordered)
        differences += _compare_tables(outcome.tables, expected.tables)

    return {
        "is_correct": outcome.error is None and not differences,
        "error": _error_payload(outcome.error) if outcome.error else None,
        "result": _result_payload(outcome.result),
        "status_message": outcome.status_message,
        "differences": differences[:MAX_DIFFERENCES],
        "checked_against_solution": has_solution,
    }
