"""O'qituvchi uchun: laboratoriya bo'yicha eng ko'p uchraydigan xatolar.

Har bir noto'g'ri urinishning tekshiruv natijasi (feedback) guruhlanadi:
- SQL xatosi — PostgreSQL xato kodi (SQLSTATE) bo'yicha, masalan «42703: bunday ustun yo'q»;
- natija farqi — xabar matni bo'yicha; undagi sonlar umumlashtiriladi («sizda 3 qator» va «sizda 5 qator» — bitta xato).

Asosiy ko'rsatkich — shu xatoga kamida bir marta duch kelgan talabalar ulushi: ko'p urinish qilgan bitta talaba
natijani buzib yubormaydi. Hisobotda talabalar ismi yo'q, faqat sonlar.
"""
import re

from .checker import ERROR_TIPS

MAX_ITEMS = 10
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
# Ikki sessiyali tekshiruvda xato matni oldiga sessiya nomi qo'shiladi
SESSION_PREFIX = re.compile(r"^[AB] sessiyasida: ")


def normalize(text):
    return NUMBER.sub("N", " ".join(str(text).split()))


def mistakes_of(feedback):
    """Bitta urinishdagi xatolar: [(kalit, turi, matn, maslahat)]."""
    feedback = feedback or {}
    error = feedback.get("error")
    if error:
        sqlstate = error.get("sqlstate") or ""
        message = SESSION_PREFIX.sub("", error.get("message") or "")
        if sqlstate:
            return [(f"sql:{sqlstate}", "error", message, error.get("tip") or ERROR_TIPS.get(sqlstate, ""))]
        return [(f"sql:{normalize(message)}", "error", message, "")]
    return [
        (f"diff:{normalize(difference)}", "difference", str(difference), "")
        for difference in feedback.get("differences") or []
    ]


def build_report(attempts, student_ids):
    """attempts — shu laboratoriyadagi urinishlar (eskisidan yangisiga), student_ids — hisobga olinadigan talabalar."""
    student_ids = set(student_ids)
    attempted, solved = set(), set()
    groups = {}
    wrong_attempts = 0
    for attempt in attempts:
        if attempt.student_id not in student_ids:
            continue
        attempted.add(attempt.student_id)
        if attempt.is_correct:
            solved.add(attempt.student_id)
            continue
        wrong_attempts += 1
        # Bitta urinishda bir xil xato ikki marta sanalmaydi
        for key, kind, text, tip in {item[0]: item for item in mistakes_of(attempt.feedback)}.values():
            group = groups.setdefault(key, {"kind": kind, "tip": tip, "attempts": 0, "students": set()})
            group["attempts"] += 1
            group["students"].add(attempt.student_id)
            group["text"] = text  # eng so'nggi ko'rinishi namuna sifatida ko'rsatiladi

    items = sorted(groups.values(), key=lambda group: (-len(group["students"]), -group["attempts"], group["text"]))
    return {
        "students": len(student_ids),
        "attempted": len(attempted),
        "solved": len(solved),
        # Urinib ko'rgan, lekin hali to'g'ri yechmagan talabalar
        "stuck": len(attempted - solved),
        "wrong_attempts": wrong_attempts,
        "items": [
            {
                "kind": group["kind"],
                "text": group["text"],
                "tip": group["tip"],
                "attempts": group["attempts"],
                "students": len(group["students"]),
                "share": round(100 * len(group["students"]) / len(attempted), 1) if attempted else 0.0,
            }
            for group in items[:MAX_ITEMS]
        ],
    }
