"""ER-diagramma chizish jarayonini tahlil qilish (process mining).

Manba: muharrir vaqti-vaqti bilan yuboradigan oraliq holatlar (ErSnapshot) va tekshirish/topshirishdagi
holatlar (LabAttempt). Ketma-ket ikki holat solishtirilib, ular orasidagi hodisalar topiladi (obyekt qo'shildi,
kardinallik o'zgardi, ...). Hodisalar mijozdan olinmaydi: server ularni diagrammalarning o'zidan hisoblaydi.

Har bir qadamda diagramma namuna bilan solishtiriladi (er.compare) — namunaga yaqinlashish egri chizig'i.
Ko'rsatkichlar va strategiya (avval_obyektlar | aralash | sinab_korish) evristik: chegaralar shu yerda,
eksport README'sida ham yozilgan. Tadqiqotchi xom ko'rsatkichlar bo'yicha o'z tasnifini qurishi mumkin.
"""
import statistics
from datetime import timedelta
from xml.sax.saxutils import quoteattr

from .er import compare, normalize

EMPTY = {"entities": [], "relationships": []}

# Talaba bitta laboratoriyada saqlay oladigan oraliq holatlar soni (muharrir har 10 soniyada yuboradi:
# ~4 soatlik faol ish). Undan keyingilari saqlanmaydi, tekshirish/topshirish esa avvalgidek yoziladi
MAX_SNAPSHOTS = 1500
# Shundan uzoq tanaffus — yangi sessiya (talaba sahifani yopib, keyinroq qaytgan)
SESSION_GAP = timedelta(minutes=30)
# Faol vaqt: ikki holat orasidagi tanaffus shundan oshsa, faqat shuncha hisoblanadi
IDLE_CAP = timedelta(minutes=5)

# Strategiya chegaralari
MIN_EVENTS = 5
TRIAL_CHURN = 0.35
TRIAL_CHECKS = 5
TRIAL_CHECK_GAP_MINUTES = 1.0
ENTITIES_FIRST_SHARE = 0.8

ACTIVITIES = {
    "obyekt_qoshildi": "Obyekt qo'shildi",
    "obyekt_ochirildi": "Obyekt o'chirildi",
    "obyekt_nomi_ozgardi": "Obyekt nomi o'zgardi",
    "atribut_qoshildi": "Atribut qo'shildi",
    "atribut_ochirildi": "Atribut o'chirildi",
    "atribut_nomi_ozgardi": "Atribut nomi o'zgardi",
    "kalit_ozgardi": "Kalit belgisi o'zgardi",
    "boglanish_qoshildi": "Bog'lanish qo'shildi",
    "boglanish_ochirildi": "Bog'lanish o'chirildi",
    "boglanish_nomi_ozgardi": "Bog'lanish nomi o'zgardi",
    "boglanish_qayta_ulandi": "Bog'lanish boshqa obyektga ulandi",
    "kardinallik_ozgardi": "Kardinallik o'zgardi",
    "joylashuv_ozgardi": "Obyektlar joyi o'zgardi",
    "tekshirish": "Tekshirish",
    "topshirish": "Baholashga topshirish",
}
CHECK_ACTIVITIES = {"run": "tekshirish", "submit": "topshirish"}
EDIT_ACTIVITIES = {"obyekt_nomi_ozgardi", "atribut_nomi_ozgardi", "kalit_ozgardi", "boglanish_nomi_ozgardi",
                   "boglanish_qayta_ulandi"}

STRATEGIES = {
    "avval_obyektlar": "Avval obyektlar, keyin bog'lanishlar",
    "aralash": "Obyekt va bog'lanishlar aralash (bosqichma-bosqich)",
    "sinab_korish": "Sinab ko'rish: ko'p o'chirish yoki tez-tez tekshirish",
    "aniqlanmadi": "Aniqlanmadi (hodisalar kam)",
}


def _attributes(entity):
    return {normalize(item["name"]): item for item in entity["attributes"]}


def _entity_events(old, new):
    events = []
    if normalize(old["name"]) != normalize(new["name"]):
        events.append(("obyekt_nomi_ozgardi", f"{old['name']} → {new['name']}"))
    before, after = _attributes(old), _attributes(new)
    added = [key for key in after if key not in before]
    removed = [key for key in before if key not in after]
    if len(added) == len(removed) == 1:
        events.append(("atribut_nomi_ozgardi", f"{new['name']}: {before[removed[0]]['name']} → {after[added[0]]['name']}"))
    else:
        events += [("atribut_qoshildi", f"{new['name']}.{after[key]['name']}") for key in added]
        events += [("atribut_ochirildi", f"{new['name']}.{before[key]['name']}") for key in removed]
    for key in after.keys() & before.keys():
        if after[key].get("key", "") != before[key].get("key", ""):
            events.append(("kalit_ozgardi", f"{new['name']}.{after[key]['name']}"))
    return events


def diff_events(before, after):
    """Ikki holat orasidagi hodisalar: [(hodisa, tafsilot)]. Obyekt va bog'lanishlar muharrir id'si bo'yicha."""
    events = []
    old_entities = {entity["id"]: entity for entity in before["entities"]}
    new_entities = {entity["id"]: entity for entity in after["entities"]}
    names = {**{key: item["name"] for key, item in old_entities.items()},
             **{key: item["name"] for key, item in new_entities.items()}}
    moved = False
    for entity in after["entities"]:
        old = old_entities.get(entity["id"])
        if old is None:
            events.append(("obyekt_qoshildi", entity["name"]))
            continue
        events += _entity_events(old, entity)
        moved = moved or (old["x"], old["y"]) != (entity["x"], entity["y"])
    for entity in before["entities"]:
        if entity["id"] not in new_entities:
            events.append(("obyekt_ochirildi", entity["name"]))

    old_relationships = {item["id"]: item for item in before["relationships"]}
    new_ids = {item["id"] for item in after["relationships"]}

    def title(relationship):
        return f"{names[relationship['source']]} — {names[relationship['target']]}"

    for relationship in after["relationships"]:
        old = old_relationships.get(relationship["id"])
        if old is None:
            events.append(("boglanish_qoshildi", title(relationship)))
            continue
        if (old["source"], old["target"]) != (relationship["source"], relationship["target"]):
            events.append(("boglanish_qayta_ulandi", f"{title(old)} → {title(relationship)}"))
        elif (old["source_card"], old["target_card"]) != (relationship["source_card"], relationship["target_card"]):
            events.append(
                (
                    "kardinallik_ozgardi",
                    f"{title(relationship)}: {old['source_card']}:{old['target_card']} → "
                    f"{relationship['source_card']}:{relationship['target_card']}",
                )
            )
        if normalize(old["name"]) != normalize(relationship["name"]):
            events.append(("boglanish_nomi_ozgardi", f"{title(relationship)}: {relationship['name'] or '—'}"))
    for relationship in before["relationships"]:
        if relationship["id"] not in new_ids:
            events.append(("boglanish_ochirildi", title(relationship)))

    if not events and moved:
        events.append(("joylashuv_ozgardi", ""))
    return events


def build_points(snapshots, attempts):
    """Bitta talaba va laboratoriya bo'yicha vaqt tartibidagi holatlar: [{"at", "source", "diagram"}]."""
    points = [{"at": item.created_at, "source": "edit", "diagram": item.diagram} for item in snapshots]
    points += [
        {"at": item.created_at, "source": "submit" if item.is_submission else "run", "diagram": item.diagram}
        for item in attempts
        if item.diagram is not None
    ]
    # Bir vaqtdagi oraliq holat tekshirishdan oldin turadi
    return sorted(points, key=lambda point: (point["at"], point["source"] != "edit"))


def analyse(points, reference):
    """Har bir holat uchun qadam: vaqt, sessiya, hodisalar va namunaga moslik (0-1)."""
    steps, previous = [], EMPTY
    session = 1
    for index, point in enumerate(points):
        if index and point["at"] - points[index - 1]["at"] > SESSION_GAP:
            session += 1
        events = diff_events(previous, point["diagram"])
        if point["source"] in CHECK_ACTIVITIES:
            events.append((CHECK_ACTIVITIES[point["source"]], ""))
        steps.append(
            {
                "at": point["at"],
                "minutes": round((point["at"] - points[0]["at"]).total_seconds() / 60, 2),
                "session": session,
                "source": point["source"],
                "events": events,
                "ratio": compare(point["diagram"], reference)["ratio"] if reference else None,
                "diagram": point["diagram"],
            }
        )
        previous = point["diagram"]
    return steps


def _minutes(delta):
    return round(delta.total_seconds() / 60, 1)


def metrics(steps):
    """Jarayon ko'rsatkichlari va strategiya. Qadam bo'lmasa None."""
    if not steps:
        return None
    start = steps[0]["at"]
    timed = [(step["at"], activity) for step in steps for activity, _ in step["events"]]
    count = {}
    for _, activity in timed:
        count[activity] = count.get(activity, 0) + 1

    active = sum(
        (min(steps[index]["at"] - steps[index - 1]["at"], IDLE_CAP) for index in range(1, len(steps))),
        timedelta(),
    )
    first_relationship = next((at for at, activity in timed if activity == "boglanish_qoshildi"), None)
    entity_times = [at for at, activity in timed if activity == "obyekt_qoshildi"]
    if not entity_times:
        entities_first = None
    elif first_relationship is None:
        entities_first = 1.0
    else:
        entities_first = round(sum(1 for at in entity_times if at <= first_relationship) / len(entity_times), 3)

    added = sum(value for key, value in count.items() if key.endswith("_qoshildi"))
    removed = sum(value for key, value in count.items() if key.endswith("_ochirildi"))
    churn = round(removed / added, 3) if added else None

    checks = [step for step in steps if step["source"] in CHECK_ACTIVITIES]
    gaps = [_minutes(checks[index]["at"] - checks[index - 1]["at"]) for index in range(1, len(checks))]
    check_gap = round(statistics.median(gaps), 1) if gaps else None

    ratios = [step["ratio"] for step in steps if step["ratio"] is not None]
    design_events = sum(value for key, value in count.items() if key not in ("tekshirish", "topshirish", "joylashuv_ozgardi"))
    if design_events < MIN_EVENTS:
        strategy = "aniqlanmadi"
    elif (churn is not None and churn >= TRIAL_CHURN) or (
        len(checks) >= TRIAL_CHECKS and check_gap is not None and check_gap < TRIAL_CHECK_GAP_MINUTES
    ):
        strategy = "sinab_korish"
    elif entities_first is not None and entities_first >= ENTITIES_FIRST_SHARE:
        strategy = "avval_obyektlar"
    else:
        strategy = "aralash"

    return {
        "steps": len(steps),
        "sessions": steps[-1]["session"],
        "total_minutes": _minutes(steps[-1]["at"] - start),
        "active_minutes": _minutes(active),
        "design_events": design_events,
        "added": added,
        "removed": removed,
        "churn": churn,
        "edits": sum(count.get(key, 0) for key in EDIT_ACTIVITIES),
        "cardinality_changes": count.get("kardinallik_ozgardi", 0),
        "first_relationship_minutes": _minutes(first_relationship - start) if first_relationship else None,
        "entities_first_share": entities_first,
        "checks": len(checks),
        "check_gap_minutes": check_gap,
        "first_check_ratio": checks[0]["ratio"] if checks else None,
        "final_ratio": ratios[-1] if ratios else None,
        "max_ratio": max(ratios) if ratios else None,
        "strategy": strategy,
    }


def process_payload(lab, snapshots, attempts):
    """O'qituvchi sahifasi (qayta ijro) uchun: qadamlar diagrammasi bilan va ko'rsatkichlar."""
    steps = analyse(build_points(snapshots, attempts), lab.reference_diagram)
    result = metrics(steps)
    return {
        "steps": [
            {
                **step,
                "events": [
                    {"activity": activity, "label": ACTIVITIES[activity], "detail": detail}
                    for activity, detail in step["events"]
                ],
            }
            for step in steps
        ],
        "metrics": result,
        "strategy_label": STRATEGIES[result["strategy"]] if result else None,
    }


def to_xes(traces):
    """IEEE XES hodisalar jurnali (ProM, pm4py). traces: [(case_id, {atribut: qiymat}, [(hodisa, vaqt)])]."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<log xes.version="1.0" xes.features="nested-attributes" xmlns="http://www.xes-standard.org/">',
        '  <extension name="Concept" prefix="concept" uri="http://www.xes-standard.org/concept.xesext"/>',
        '  <extension name="Time" prefix="time" uri="http://www.xes-standard.org/time.xesext"/>',
        '  <global scope="event"><string key="concept:name" value=""/>'
        '<date key="time:timestamp" value="1970-01-01T00:00:00+00:00"/></global>',
    ]
    for case_id, attributes, events in traces:
        lines.append("  <trace>")
        lines.append(f'    <string key="concept:name" value={quoteattr(case_id)}/>')
        for key, value in attributes.items():
            lines.append(f"    <string key={quoteattr(key)} value={quoteattr(str(value))}/>")
        for activity, moment in events:
            lines.append(
                f'    <event><string key="concept:name" value={quoteattr(activity)}/>'
                f'<date key="time:timestamp" value="{moment.isoformat()}"/></event>'
            )
        lines.append("  </trace>")
    lines.append("</log>")
    return "\n".join(lines) + "\n"
