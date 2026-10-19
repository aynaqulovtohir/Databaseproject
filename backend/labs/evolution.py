"""Sxemani rivojlantirish (migratsiya) laboratoriyasi: talablar o'zgardi, mavjud baza ma'lumot yo'qotmasdan yangilanadi.

Boshlang'ich jadvallar (setup_sql) — eski sxema va ma'lumotlar. Talaba migratsiya yozadi (ALTER TABLE, yangi jadval,
ma'lumotni ko'chirish). Tekshiruv:
1. migratsiyadan keyingi jadvallar (tuzilishi, cheklovlari va qatorlari) namunaviy migratsiyadagi bilan bir xil —
   ma'lumot yo'qolmagan va to'g'ri ko'chirilgan;
2. ilovaning yangi so'rovlari (check_queries) xatosiz bajariladi va namunaviy migratsiyadagi natijani beradi;
3. yashirin ma'lumotlarda (hidden_setup_sql) ham shunday — qiymatlarni qo'lda INSERT qilib aldab bo'lmaydi.

So'rovlar talaba kodidan keyin alohida tranzaksiyada bajariladi va orqaga qaytariladi (sandbox.run_followups). So'rov bir
nechta buyruqdan iborat bo'lishi mumkin, oxirgisi SELECT: masalan, UPDATE dan keyin trigger yozgan tarix jadvalini yoki
INSERT dan keyin view'ni o'qish. Shu bilan view, funksiya va trigger laboratoriyalari ham tekshiriladi.
"""
import re

from .checker import (
    HIDDEN_MISMATCH,
    LabSetupError,
    _compare_results,
    _compare_tables,
    _error_payload,
    _plan_payload,
    _result_payload,
)
from .probes import TRANSACTION_CONTROL, message
from .sandbox import SqlError, run_followups, split_statements

MAX_QUERIES = 10
MAX_QUERY_SQL = 2000
MAX_TITLE = 200
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,20}$")
ORDER_BY = re.compile(r"\border\s+by\b", re.IGNORECASE)
FINAL_SELECT = re.compile(r"^\(?\s*(SELECT|WITH|VALUES|TABLE)\b", re.IGNORECASE)


class QueriesError(ValueError):
    """So'rovlar ro'yxati noto'g'ri (o'qituvchiga ko'rsatiladigan xabar bilan)."""


def validate_queries(value):
    """Tuzilishini tekshiradi va toza nusxasini qaytaradi (sandboxsiz)."""
    if not isinstance(value, list):
        raise QueriesError("So'rovlar ro'yxat ko'rinishida bo'lishi kerak.")
    if len(value) > MAX_QUERIES:
        raise QueriesError(f"So'rovlar {MAX_QUERIES} tadan oshmasligi kerak.")
    clean, ids = [], set()
    for item in value:
        if not isinstance(item, dict):
            raise QueriesError("So'rov noto'g'ri formatda.")
        query_id = item.get("id")
        if not isinstance(query_id, str) or not ID_PATTERN.match(query_id) or query_id in ids:
            raise QueriesError("So'rov identifikatori (harf, raqam, _ yoki -; 20 belgigacha) takrorlanmasligi kerak.")
        ids.add(query_id)
        title = item.get("title")
        if not isinstance(title, str) or not title.strip() or len(title) > MAX_TITLE:
            raise QueriesError(f"«{query_id}» so'rovining nomi bo'sh bo'lmasligi va {MAX_TITLE} belgidan oshmasligi kerak.")
        sql = item.get("sql")
        if not isinstance(sql, str) or not sql.strip() or len(sql) > MAX_QUERY_SQL:
            raise QueriesError(f"«{query_id}» so'rovining SQL'i bo'sh bo'lmasligi va {MAX_QUERY_SQL} belgidan oshmasligi kerak.")
        statements = split_statements(sql)
        if not statements or not FINAL_SELECT.match(statements[-1]):
            raise QueriesError(f"«{query_id}» — oxirgi buyruq natija qaytaradigan so'rov (SELECT) bo'lishi kerak.")
        if any(TRANSACTION_CONTROL.match(statement) for statement in statements):
            raise QueriesError(f"«{query_id}» so'rovida tranzaksiya buyruqlari bo'lmasligi kerak.")
        clean.append({"id": query_id, "title": " ".join(title.split()), "sql": ";\n".join(statements)})
    return clean


def _run(script, setup_sql, queries, field="solution_sql"):
    outcome, results = run_followups(script, setup_sql, [query["sql"] for query in queries])
    if outcome.setup_failed:
        raise LabSetupError("hidden_setup_sql" if field == "hidden" else "setup_sql", outcome.error)
    return outcome, results


def _query_differences(query, student, expected):
    """Bitta so'rov: talaba migratsiyasidan keyin xato yoki natija farqi (matn) yoki None."""
    error, result = student
    if error is not None:
        return f"Xato berdi: {message(error)}"
    differences = _compare_results(result, expected[1], bool(ORDER_BY.search(query["sql"])))
    return differences[0] if differences else None


def validate_lab_queries(setup_sql, solution_sql, hidden_setup_sql, queries):
    """Saqlashdan oldin: namunaviy migratsiyadan keyin har bir so'rov ishlaydi (yashirin ma'lumotlarda ham); migratsiyasiz
    esa xato beradi yoki boshqa natija qaytaradi — aks holda so'rov migratsiyani tekshirmaydi."""
    if not solution_sql.strip():
        raise LabSetupError("solution_sql", SqlError("Migratsiya laboratoriyasida namunaviy migratsiya bo'lishi kerak."))
    setups = [("setup_sql", setup_sql)] + ([("hidden", hidden_setup_sql)] if hidden_setup_sql.strip() else [])
    for field, setup in setups:
        migrated, after = _run(solution_sql, setup, queries, field)
        if migrated.error:
            raise LabSetupError("solution_sql", migrated.error)
        for query, (error, _) in zip(queries, after):
            if error is not None:
                raise LabSetupError("check_queries", SqlError(f"«{query['title']}» namunaviy migratsiyadan keyin xato berdi: {message(error)}"))
    _, before = _run("SELECT 1", setup_sql, queries)
    _, after = _run(solution_sql, setup_sql, queries)
    for query, old, new in zip(queries, before, after):
        if old[0] is None and not _compare_results(old[1], new[1], True):
            raise LabSetupError(
                "check_queries",
                SqlError(f"«{query['title']}» migratsiyasiz ham xuddi shu natijani beradi — u migratsiyani tekshirmaydi."),
            )


def check_evolution(lab, sql_code):
    """Talaba migratsiyasini tekshiradi; natija check_code bilan bir xil ko'rinishda, qo'shimcha "queries" bilan."""
    queries = lab.check_queries
    student, student_results = _run(sql_code, lab.setup_sql, queries)
    expected, expected_results = _run(lab.solution_sql, lab.setup_sql, queries)
    if expected.error:
        raise LabSetupError("solution_sql", expected.error)

    differences, items = [], []
    if student.error is None:
        differences = _compare_tables(student.tables, expected.tables)
        for query, mine, wanted in zip(queries, student_results, expected_results):
            problem = _query_differences(query, mine, wanted)
            items.append({"id": query["id"], "title": query["title"], "passed": problem is None, "message": problem or ""})
            if problem:
                differences.append(f"«{query['title']}» so'rovi: {problem}")
        if not differences and lab.hidden_setup_sql.strip() and not _passes_hidden(lab, sql_code):
            differences.append(HIDDEN_MISMATCH)
    return {
        "is_correct": student.error is None and not differences,
        "error": _error_payload(student.error) if student.error else None,
        "result": _result_payload(student.result),
        "status_message": student.status_message,
        "differences": differences,
        "checked_against_solution": True,
        "plan": _plan_payload(student),
        "queries": items,
    }


def _passes_hidden(lab, sql_code):
    """Yashirin ma'lumotlarda: jadvallar va so'rovlar natijasi namunaviy migratsiyadagi bilan bir xil (tafsilotsiz)."""
    student, student_results = _run(sql_code, lab.hidden_setup_sql, lab.check_queries, "hidden")
    if student.error:
        return False
    expected, expected_results = _run(lab.solution_sql, lab.hidden_setup_sql, lab.check_queries, "hidden")
    if expected.error:
        raise LabSetupError("solution_sql", expected.error)
    if _compare_tables(student.tables, expected.tables):
        return False
    return all(
        _query_differences(query, mine, wanted) is None
        for query, mine, wanted in zip(lab.check_queries, student_results, expected_results)
    )
