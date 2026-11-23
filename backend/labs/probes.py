"""Yaxlitlik cheklovlari laboratoriyasi: talaba yozgan cheklovlar noto'g'ri ma'lumotni to'xtatadimi.

Talaba boshlang'ich jadvallarga (setup_sql) cheklovlar qo'shadi: CHECK, FOREIGN KEY, UNIQUE, NOT NULL yoki trigger.
Keyin har bir sinov alohida tranzaksiyada bajariladi va orqaga qaytariladi (sandbox.run_probes):
- "attack" — noto'g'ri ma'lumot: cheklov xatosi bilan rad etilishi kerak;
- "valid" — to'g'ri ma'lumot: xatosiz qabul qilinishi kerak ("hamma narsani taqiqlash" bilan aldab bo'lmaydi).

Faqat yaxlitlik buzilishi (SQLSTATE 23xxx) yoki trigger'dagi RAISE EXCEPTION (P0001) "to'xtatildi" hisoblanadi:
jadvalni o'chirib yoki ustun nomini o'zgartirib hujumni "to'xtatish" (42xxx xatolari) o'tmaydi.

Yashirin sinovlar talabaga faqat soni bilan ko'rsatiladi: ko'rinadigan hujumga moslab yozilgan tor cheklov
(masalan, CHECK (narx <> -5)) yashirin hujumda ushlanadi. Ularning xato matni ham ko'rsatilmaydi (qiymatlarni ochadi).
"""
import re

from .checker import LabSetupError, _error_payload, _plan_payload, _result_payload
from .sandbox import SqlError, run_probes, split_statements
from config.i18n import tr

KINDS = ("attack", "valid")
MAX_PROBES = 20
MAX_PROBE_SQL = 2000
MAX_TITLE = 200
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,20}$")
# Sinov o'z tranzaksiyasini boshqarmasin: aks holda o'zgarish orqaga qaytmay, keyingi sinovlarga ta'sir qiladi
TRANSACTION_CONTROL = re.compile(r"^(BEGIN|COMMIT|ROLLBACK|END|START|SAVEPOINT|RELEASE|ABORT|PREPARE)\b", re.IGNORECASE)


class ProbesError(ValueError):
    """Sinovlar ro'yxati noto'g'ri (o'qituvchiga ko'rsatiladigan xabar bilan)."""


def message(error):
    """Xato matni qator raqamisiz: sinov o'z tranzaksiyasi ichida bajariladi, raqam o'qituvchi yozgan SQL'ga mos kelmaydi."""
    return f"{error.message} ({error.detail})" if error.detail else error.message


def blocked(error):
    """Xato cheklov tomonidan berilganmi: yaxlitlik buzilishi yoki trigger'dagi RAISE EXCEPTION."""
    return error is not None and (error.sqlstate.startswith("23") or error.sqlstate == "P0001")


def passed(probe, error):
    return blocked(error) if probe["kind"] == "attack" else error is None


def validate_probes(value):
    """Tuzilishini tekshiradi va toza nusxasini qaytaradi (sandboxsiz)."""
    if not isinstance(value, list):
        raise ProbesError(tr("Sinovlar ro'yxat ko'rinishida bo'lishi kerak."))
    if len(value) > MAX_PROBES:
        raise ProbesError(tr("Sinovlar {MAX_PROBES} tadan oshmasligi kerak.", MAX_PROBES=MAX_PROBES))
    clean, ids = [], set()
    for item in value:
        if not isinstance(item, dict):
            raise ProbesError(tr("Sinov noto'g'ri formatda."))
        probe_id = item.get("id")
        if not isinstance(probe_id, str) or not ID_PATTERN.match(probe_id) or probe_id in ids:
            raise ProbesError(tr("Sinov identifikatori (harf, raqam, _ yoki -; 20 belgigacha) takrorlanmasligi kerak."))
        ids.add(probe_id)
        title = item.get("title")
        if not isinstance(title, str) or not title.strip() or len(title) > MAX_TITLE:
            raise ProbesError(tr("«{probe_id}» sinovining nomi bo'sh bo'lmasligi va {MAX_TITLE} belgidan oshmasligi kerak.", probe_id=probe_id, MAX_TITLE=MAX_TITLE))
        if item.get("kind") not in KINDS:
            raise ProbesError(tr("«{probe_id}» sinovining turi «attack» yoki «valid» bo'lishi kerak.", probe_id=probe_id))
        sql = item.get("sql")
        if not isinstance(sql, str) or not sql.strip() or len(sql) > MAX_PROBE_SQL:
            raise ProbesError(tr("«{probe_id}» sinovining SQL'i bo'sh bo'lmasligi va {MAX_PROBE_SQL} belgidan oshmasligi kerak.", probe_id=probe_id, MAX_PROBE_SQL=MAX_PROBE_SQL))
        if any(TRANSACTION_CONTROL.match(statement) for statement in split_statements(sql)):
            raise ProbesError(tr("«{probe_id}» sinovida tranzaksiya buyruqlari (BEGIN, COMMIT, ROLLBACK...) bo'lmasligi kerak.", probe_id=probe_id))
        clean.append(
            {
                "id": probe_id,
                "title": " ".join(title.split()),
                "kind": item["kind"],
                "sql": sql.strip(),
                "hidden": bool(item.get("hidden", False)),
            }
        )
    if clean and not any(probe["kind"] == "attack" for probe in clean):
        raise ProbesError(tr("Kamida bitta hujum (attack) sinovi bo'lishi kerak."))
    return clean


def validate_lab_probes(setup_sql, solution_sql, probes):
    """Laboratoriyani saqlashdan oldin: har bir hujum cheklovsiz o'tadi, namunaviy yechim esa barcha sinovlardan o'tadi."""
    if not solution_sql.strip():
        raise LabSetupError("solution_sql", SqlError(tr("Cheklovlar laboratoriyasida namunaviy yechim (cheklovlar) bo'lishi kerak.")))
    sqls = [probe["sql"] for probe in probes]
    outcome, errors = run_probes("SELECT 1", setup_sql, sqls)
    if outcome.error:
        raise LabSetupError("setup_sql", outcome.error)
    for probe, error in zip(probes, errors):
        if probe["kind"] == "attack" and error is not None:
            raise LabSetupError(
                "probes",
                SqlError(tr("«{title}» hujumi cheklovsiz ham bajarilmadi — u sinov bo'la olmaydi: {error}", title=probe['title'], error=message(error))),
            )
        if probe["kind"] == "valid" and error is not None:
            raise LabSetupError("probes", SqlError(tr("«{title}» to'g'ri ma'lumoti boshlang'ich jadvallarda xato berdi: {error}", title=probe['title'], error=message(error))))
    outcome, errors = run_probes(solution_sql, setup_sql, sqls)
    if outcome.error:
        raise LabSetupError("solution_sql", outcome.error)
    for probe, error in zip(probes, errors):
        if not passed(probe, error):
            what = "to'xtatmadi" if probe["kind"] == "attack" else tr("rad etdi")
            detail = f": {message(error)}" if error else ""
            raise LabSetupError("probes", SqlError(tr("Namunaviy yechim «{title}» sinovini {what}{detail}", title=probe['title'], what=what, detail=detail)))


def _item(probe, error):
    ok = passed(probe, error)
    if probe["kind"] == "attack":
        # To'xtatilmagan hujumda boshqa xato (jadval yo'q, vaqt tugadi) bo'lsa — o'sha, aks holda ma'lumot qabul qilingan
        text = message(error) if error else tr("Ma'lumot qabul qilindi — cheklov uni to'xtatmadi.")
    else:
        text = "" if ok else message(error)
    return {"id": probe["id"], "title": probe["title"], "kind": probe["kind"], "passed": ok, "message": text}


def check_probes(lab, sql_code):
    """Talaba kodini tekshiradi; natija check_code bilan bir xil ko'rinishda, qo'shimcha "probes" va "ratio" bilan."""
    probes = lab.probes
    outcome, errors = run_probes(sql_code, lab.setup_sql, [probe["sql"] for probe in probes])
    if outcome.setup_failed:
        raise LabSetupError("setup_sql", outcome.error)
    results = [(probe, error, passed(probe, error)) for probe, error in zip(probes, errors)]
    visible = [_item(probe, error) for probe, error, _ in results if not probe.get("hidden")]
    hidden = [ok for probe, _, ok in results if probe.get("hidden")]

    differences = []
    for item in visible:
        if not item["passed"]:
            what = tr("o'tib ketdi") if item["kind"] == "attack" else tr("rad etildi, lekin u to'g'ri ma'lumot")
            differences.append(f"«{item['title']}» — {what}.")
    if hidden and not all(hidden):
        differences.append(
            tr("Yashirin sinovlardan {value} tasi o'tmadi: cheklov faqat ko'rinadigan misollarga emas, qoidaning o'ziga mos bo'lsin.", value=len(hidden) - sum(hidden))
        )
    total = len(results)
    ratio = round(sum(ok for _, _, ok in results) / total, 3) if total and outcome.error is None else 0.0
    return {
        "is_correct": outcome.error is None and total > 0 and all(ok for _, _, ok in results),
        "error": _error_payload(outcome.error) if outcome.error else None,
        "result": _result_payload(outcome.result),
        "status_message": outcome.status_message,
        "differences": differences,
        "checked_against_solution": True,
        "plan": _plan_payload(outcome),
        "probes": visible if outcome.error is None else [],
        "hidden_probes": {"total": len(hidden), "passed": sum(hidden)} if outcome.error is None else None,
        "ratio": ratio,
    }
