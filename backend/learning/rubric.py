"""Baholash rubrikasi va bosqichli loyiha qoidalari.

Rubrika — mezonlar ro'yxati, ballar yig'indisi 100. Bosqichli loyihada har bir mezon bitta bosqichga
tegishli va har bir bosqichda kamida bitta mezon bor: bosqich bahosi — uning mezonlari ballari yig'indisi,
loyiha bahosi — barcha bosqichlar yig'indisi.
"""
from grading.models import MAX_SCORE
from config.i18n import tr

MAX_CRITERIA = 20
MAX_STAGES = 8
MAX_NAME_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 1000


class RubricError(ValueError):
    pass


def clean_rubric(rubric, stage_count):
    """Rubrikani tekshiradi va faqat ma'lum maydonlardan iborat toza nusxasini qaytaradi."""
    if rubric in (None, ""):
        rubric = []
    if not isinstance(rubric, list):
        raise RubricError(tr("Rubrika mezonlar ro'yxati bo'lishi kerak."))
    if not rubric:
        if stage_count:
            raise RubricError(tr("Bosqichli loyihada rubrika kerak: har bir bosqich o'z mezonlari bo'yicha baholanadi."))
        return []
    if len(rubric) > MAX_CRITERIA:
        raise RubricError(tr("Rubrikada {MAX_CRITERIA} tadan ko'p mezon bo'lmasin.", MAX_CRITERIA=MAX_CRITERIA))

    cleaned = []
    for number, item in enumerate(rubric, start=1):
        if not isinstance(item, dict):
            raise RubricError(tr("{number}-mezon noto'g'ri formatda.", number=number))
        name = str(item.get("name") or "").strip()
        description = str(item.get("description") or "").strip()
        points = item.get("points")
        stage = item.get("stage")
        if not name or len(name) > MAX_NAME_LENGTH:
            raise RubricError(tr("{number}-mezon nomi 1–{MAX_NAME_LENGTH} belgi bo'lsin.", number=number, MAX_NAME_LENGTH=MAX_NAME_LENGTH))
        if len(description) > MAX_DESCRIPTION_LENGTH:
            raise RubricError(tr("{number}-mezon izohi {MAX_DESCRIPTION_LENGTH} belgidan oshmasin.", number=number, MAX_DESCRIPTION_LENGTH=MAX_DESCRIPTION_LENGTH))
        if isinstance(points, bool) or not isinstance(points, int) or not 1 <= points <= MAX_SCORE:
            raise RubricError(tr("«{name}» mezoni bali 1 dan {MAX_SCORE} gacha butun son bo'lsin.", name=name, MAX_SCORE=MAX_SCORE))
        if stage_count:
            if isinstance(stage, bool) or not isinstance(stage, int) or not 0 <= stage < stage_count:
                raise RubricError(tr("«{name}» mezoni uchun bosqichni tanlang.", name=name))
        else:
            stage = None
        cleaned.append({"name": name, "points": points, "description": description, "stage": stage})

    total = sum(item["points"] for item in cleaned)
    if total != MAX_SCORE:
        raise RubricError(tr("Mezonlar ballari yig'indisi {MAX_SCORE} bo'lishi kerak (hozir {total}).", MAX_SCORE=MAX_SCORE, total=total))
    if stage_count:
        empty = sorted(set(range(stage_count)) - {item["stage"] for item in cleaned})
        if empty:
            raise RubricError(tr("{value}-bosqichga birorta ham mezon biriktirilmagan.", value=empty[0] + 1))
    return cleaned


def criteria_for(assignment, stage):
    """Shu yechim (bosqich) qaysi mezonlar bo'yicha baholanadi."""
    order = stage.order if stage else None
    return [item for item in assignment.rubric if item.get("stage") == order]


def structure(rubric):
    """Yechimlar kelgandan keyin o'zgartirib bo'lmaydigan qism: ballar va bosqichga biriktirish."""
    return [(item["points"], item["stage"]) for item in rubric]
