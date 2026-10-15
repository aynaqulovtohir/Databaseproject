"""ER-diagramma laboratoriyasi: diagrammani tekshirish, namuna bilan solishtirish va tuzatish.

Diagramma JSON ko'rinishida saqlanadi:
    {
      "entities": [
        {"id": "e1", "name": "Talaba", "x": 40, "y": 60,
         "attributes": [{"name": "id", "key": "pk"}, {"name": "ism", "key": ""}]}
      ],
      "relationships": [
        {"id": "r1", "name": "a'zo", "source": "e1", "target": "e2", "source_card": "N", "target_card": "1"}
      ]
    }
Kardinallik har bir uchida "1" yoki "N": shu obyektning nechta nusxasi bog'lanishda qatnashadi.
Masalan, Talaba (N) — Guruh (1): bitta guruhda ko'p talaba, har bir talaba bitta guruhda.

Solishtirish nomlar bo'yicha (katta-kichik harf, bo'sh joy va apostrof turlari farqlanmaydi).
"key": "fk" bo'lgan atributlar solishtirilmaydi: konseptual modelda ularni bog'lanish ifodalaydi.

Ishlash davomidagi farqlar to'g'ri javobni oshkor qilmaydi (masalan, "2 ta atribut yetishmaydi").
To'liq tuzatilgan diagramma (build_fixed) faqat baholashga topshirilgandan keyin ko'rsatiladi.
"""
import math
import re

CARDINALITIES = ("1", "N")
KEYS = ("pk", "fk", "")
MAX_ENTITIES = 40
MAX_ATTRIBUTES = 40
MAX_RELATIONSHIPS = 80
MAX_NAME_LENGTH = 64
MAX_ID_LENGTH = 64
MAX_COORDINATE = 100_000
# Tuzatilgan diagrammada yangi qo'shilgan obyektlar talaba chizganlarining o'ng tomoniga joylashtiriladi
ADDED_ENTITY_OFFSET_X = 300
ADDED_ENTITY_STEP_Y = 220

APOSTROPHES = re.compile(r"[ʻʼ‘’`´]")
SEPARATORS = re.compile(r"[\s_\-]+")


class DiagramError(ValueError):
    """Diagramma noto'g'ri tuzilgan (talabaga ko'rsatiladigan xabar bilan)."""


def normalize(name):
    """Nomlarni solishtirish uchun: "Material fayli", "material_fayli" va "MATERIAL-FAYLI" bir xil."""
    text = APOSTROPHES.sub("'", name).strip().lower()
    return SEPARATORS.sub("_", text)


def _name(value, what):
    if not isinstance(value, str) or not value.strip():
        raise DiagramError(f"{what} nomi bo'sh bo'lmasligi kerak.")
    value = " ".join(value.split())
    if len(value) > MAX_NAME_LENGTH:
        raise DiagramError(f"{what} nomi {MAX_NAME_LENGTH} belgidan oshmasligi kerak: «{value[:20]}…».")
    return value


def _identifier(value, what):
    if not isinstance(value, str) or not value or len(value) > MAX_ID_LENGTH:
        raise DiagramError(f"{what} identifikatori noto'g'ri.")
    return value


def _coordinate(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return 0
    return max(-MAX_COORDINATE, min(MAX_COORDINATE, round(value)))


def validate_diagram(data):
    """Diagrammani tekshiradi va faqat ma'lum maydonlardan iborat toza nusxasini qaytaradi."""
    if not isinstance(data, dict):
        raise DiagramError("Diagramma noto'g'ri formatda.")
    entities = data.get("entities")
    relationships = data.get("relationships", [])
    if not isinstance(entities, list) or not isinstance(relationships, list):
        raise DiagramError("Diagramma noto'g'ri formatda.")
    if len(entities) > MAX_ENTITIES:
        raise DiagramError(f"Obyektlar soni {MAX_ENTITIES} tadan oshmasligi kerak.")
    if len(relationships) > MAX_RELATIONSHIPS:
        raise DiagramError(f"Bog'lanishlar soni {MAX_RELATIONSHIPS} tadan oshmasligi kerak.")

    clean_entities, entity_ids, entity_names = [], set(), set()
    for entity in entities:
        if not isinstance(entity, dict):
            raise DiagramError("Obyekt noto'g'ri formatda.")
        entity_id = _identifier(entity.get("id"), "Obyekt")
        name = _name(entity.get("name"), "Obyekt")
        if entity_id in entity_ids:
            raise DiagramError("Ikki obyektning identifikatori bir xil.")
        if normalize(name) in entity_names:
            raise DiagramError(f"«{name}» nomli obyekt ikki marta chizilgan.")
        entity_ids.add(entity_id)
        entity_names.add(normalize(name))

        attributes = entity.get("attributes", [])
        if not isinstance(attributes, list) or len(attributes) > MAX_ATTRIBUTES:
            raise DiagramError(f"«{name}» obyektida atributlar {MAX_ATTRIBUTES} tadan oshmasligi kerak.")
        clean_attributes, attribute_names = [], set()
        for attribute in attributes:
            if not isinstance(attribute, dict):
                raise DiagramError(f"«{name}» obyektida atribut noto'g'ri formatda.")
            attribute_name = _name(attribute.get("name"), f"«{name}» obyektidagi atribut")
            if normalize(attribute_name) in attribute_names:
                raise DiagramError(f"«{name}» obyektida «{attribute_name}» atributi ikki marta yozilgan.")
            attribute_names.add(normalize(attribute_name))
            key = attribute.get("key", "")
            clean_attributes.append({"name": attribute_name, "key": key if key in KEYS else ""})

        clean_entities.append(
            {
                "id": entity_id,
                "name": name,
                "x": _coordinate(entity.get("x")),
                "y": _coordinate(entity.get("y")),
                "attributes": clean_attributes,
            }
        )

    clean_relationships, relationship_ids = [], set()
    for relationship in relationships:
        if not isinstance(relationship, dict):
            raise DiagramError("Bog'lanish noto'g'ri formatda.")
        relationship_id = _identifier(relationship.get("id"), "Bog'lanish")
        if relationship_id in relationship_ids:
            raise DiagramError("Ikki bog'lanishning identifikatori bir xil.")
        relationship_ids.add(relationship_id)
        source, target = relationship.get("source"), relationship.get("target")
        if source not in entity_ids or target not in entity_ids:
            raise DiagramError("Bog'lanish mavjud bo'lmagan obyektga ulangan.")
        cards = relationship.get("source_card"), relationship.get("target_card")
        if any(card not in CARDINALITIES for card in cards):
            raise DiagramError("Bog'lanish kardinalligi «1» yoki «N» bo'lishi kerak.")
        name = relationship.get("name") or ""
        if not isinstance(name, str) or len(name) > MAX_NAME_LENGTH:
            raise DiagramError(f"Bog'lanish nomi {MAX_NAME_LENGTH} belgidan oshmasligi kerak.")
        clean_relationships.append(
            {
                "id": relationship_id,
                "name": " ".join(name.split()),
                "source": source,
                "target": target,
                "source_card": cards[0],
                "target_card": cards[1],
            }
        )
    return {"entities": clean_entities, "relationships": clean_relationships}


# ---------- Solishtirish ----------


def _index(diagram):
    """Nom bo'yicha obyektlar va obyekt nomlari bilan ifodalangan bog'lanishlar."""
    entities = {normalize(entity["name"]): entity for entity in diagram["entities"]}
    names_by_id = {entity["id"]: normalize(entity["name"]) for entity in diagram["entities"]}
    relationships = []
    for relationship in diagram["relationships"]:
        relationships.append(
            {
                **relationship,
                "a": names_by_id[relationship["source"]],
                "b": names_by_id[relationship["target"]],
                "ca": relationship["source_card"],
                "cb": relationship["target_card"],
            }
        )
    return entities, relationships


def _attributes(entity):
    """FK'dan boshqa atributlar: normallashgan nom -> atribut."""
    return {normalize(item["name"]): item for item in entity["attributes"] if item.get("key", "") != "fk"}


def _primary_key(entity):
    return {normalize(item["name"]) for item in entity["attributes"] if item.get("key", "") == "pk"}


def _cards_from(relationship, first):
    """Bog'lanish kardinalligi `first` obyekt tomonidan qaraganda: (first tomoni, ikkinchi tomon)."""
    if relationship["a"] == first:
        return relationship["ca"], relationship["cb"]
    return relationship["cb"], relationship["ca"]


def _pair(relationship):
    return tuple(sorted((relationship["a"], relationship["b"])))


def _match_relationships(student_relationships, reference_relationships, common):
    """Ikkala diagrammada ham bor obyektlar orasidagi bog'lanishlarni juftlaydi.

    Qaytaradi: (juftlar [(talaba, namuna)], yetishmaydiganlar, ortiqchalar).
    """
    by_pair = {}
    for relationship in reference_relationships:
        if relationship["a"] in common and relationship["b"] in common:
            by_pair.setdefault(_pair(relationship), []).append(relationship)
    pairs, extra = [], []
    for relationship in student_relationships:
        if relationship["a"] not in common or relationship["b"] not in common:
            continue
        candidates = by_pair.get(_pair(relationship), [])
        if not candidates:
            extra.append(relationship)
            continue
        # Avval kardinalligi ham mos keladigani, bo'lmasa birinchisi olinadi
        exact = next(
            (item for item in candidates if _cards_from(item, relationship["a"]) == (relationship["ca"], relationship["cb"])),
            candidates[0],
        )
        candidates.remove(exact)
        pairs.append((relationship, exact))
    missing = [item for items in by_pair.values() for item in items]
    return pairs, missing, extra


def _display(entities, key):
    return entities[key]["name"]


def _associative_entities(student_relationships, missing, extra_names):
    """M:N bog'lanishni oraliq obyekt orqali chizgan holatlar: {namuna bog'lanish id: oraliq obyekt nomi}."""
    found = {}
    for relationship in missing:
        if (relationship["ca"], relationship["cb"]) != ("N", "N") or relationship["a"] == relationship["b"]:
            continue
        for candidate in extra_names:
            links = {}
            for item in student_relationships:
                if candidate in (item["a"], item["b"]):
                    other = item["b"] if item["a"] == candidate else item["a"]
                    links[other] = _cards_from(item, candidate)
            if links.get(relationship["a"]) == ("N", "1") and links.get(relationship["b"]) == ("N", "1"):
                found[relationship["id"]] = candidate
                break
    return found


def compare(student, reference):
    """Talaba diagrammasini namuna bilan solishtiradi.

    Qaytaradi: {"differences": [matnlar], "ratio": 0..1 (qisman to'g'rilik darajasi)}.
    """
    student_entities, student_relationships = _index(student)
    reference_entities, reference_relationships = _index(reference)
    common = student_entities.keys() & reference_entities.keys()
    missing_entities = reference_entities.keys() - student_entities.keys()
    extra_entities = student_entities.keys() - reference_entities.keys()

    pairs, missing_relationships, extra_relationships = _match_relationships(
        student_relationships, reference_relationships, common
    )
    associative = _associative_entities(student_relationships, missing_relationships, extra_entities)
    # Oraliq obyekt orqali ifodalangan M:N: uning o'zi va bog'lanishlari alohida xato sifatida sanalmaydi
    associative_names = set(associative.values())
    missing_relationships = [item for item in missing_relationships if item["id"] not in associative]

    differences = []
    total = matched = extras = 0

    if missing_entities:
        differences.append(f"{len(missing_entities)} ta obyekt yetishmaydi.")
    for name in sorted(extra_entities - associative_names):
        differences.append(f"Ortiqcha obyekt: «{_display(student_entities, name)}».")
        extras += 1
    total += len(reference_entities)
    matched += len(common)

    for name in sorted(common):
        mine, wanted = student_entities[name], reference_entities[name]
        title = mine["name"]
        my_attributes, wanted_attributes = _attributes(mine), _attributes(wanted)
        missing_attributes = wanted_attributes.keys() - my_attributes.keys()
        extra_attributes = my_attributes.keys() - wanted_attributes.keys()
        if missing_attributes:
            differences.append(f"«{title}» obyektida {len(missing_attributes)} ta atribut yetishmaydi.")
        if extra_attributes:
            names = ", ".join(my_attributes[key]["name"] for key in sorted(extra_attributes))
            differences.append(f"«{title}» obyektida ortiqcha atribut: {names}.")
        total += len(wanted_attributes) + 1
        matched += len(wanted_attributes.keys() & my_attributes.keys())
        extras += len(extra_attributes)

        my_key, wanted_key = _primary_key(mine), _primary_key(wanted)
        if my_key == wanted_key:
            matched += 1
        elif not my_key:
            differences.append(f"«{title}» obyektida asosiy kalit (PK) belgilanmagan.")
        else:
            differences.append(f"«{title}» obyektining asosiy kaliti (PK) noto'g'ri tanlangan.")

    for relationship_id, name in associative.items():
        wanted = next(item for item in reference_relationships if item["id"] == relationship_id)
        differences.append(
            f"«{_display(reference_entities, wanted['a'])}» va «{_display(reference_entities, wanted['b'])}» "
            f"orasidagi ko'p-ko'p (M:N) bog'lanishni «{_display(student_entities, name)}» oraliq obyekti orqali "
            "ifodalagansiz. Mantiqan bu to'g'ri, lekin bu laboratoriyada M:N bog'lanishni ikki obyekt orasida "
            "to'g'ridan-to'g'ri chizing."
        )

    total += len(reference_relationships)
    for mine, wanted in pairs:
        my_cards = _cards_from(mine, wanted["a"])
        if my_cards == (wanted["ca"], wanted["cb"]):
            matched += 1
            continue
        differences.append(
            f"«{_display(student_entities, wanted['a'])}» — «{_display(student_entities, wanted['b'])}» "
            f"bog'lanishining kardinalligi noto'g'ri (sizda {my_cards[0]}:{my_cards[1]}). Bitta "
            f"«{_display(student_entities, wanted['a'])}» nechta «{_display(student_entities, wanted['b'])}» "
            "bilan bog'lanishini va aksincha qayta o'ylang."
        )
        matched += 0.5
    for wanted in missing_relationships:
        differences.append(
            f"«{_display(student_entities, wanted['a'])}» va «{_display(student_entities, wanted['b'])}» "
            "orasida bog'lanish yetishmaydi."
        )
    for mine in extra_relationships:
        if mine["a"] in associative_names or mine["b"] in associative_names:
            continue
        differences.append(
            f"«{_display(student_entities, mine['a'])}» va «{_display(student_entities, mine['b'])}» "
            "orasida ortiqcha bog'lanish bor."
        )
        extras += 1

    if not student["entities"]:
        differences = ["Diagramma bo'sh: kamida bitta obyekt chizing."]
    ratio = max(0.0, matched - 0.5 * extras) / total if total else 0.0
    return {"differences": differences, "ratio": round(min(ratio, 1.0), 3)}


# ---------- Tuzatish (baholashga topshirilgandan keyin ko'rsatiladi) ----------


def _card_text(first, second):
    return "M:N" if (first, second) == ("N", "N") else f"{first}:{second}"


def build_fixed(student, reference):
    """Talaba diagrammasini namunaga moslab tuzatadi va har bir o'zgarishni belgilaydi.

    Talabaning joylashuvi va nomlari saqlanadi. Har bir obyekt, atribut va bog'lanishda
    "status": "ok" | "added" | "removed" | "changed". "changes" — o'zgarishlar ro'yxati (matn).
    """
    student_entities, student_relationships = _index(student)
    reference_entities, reference_relationships = _index(reference)
    common = student_entities.keys() & reference_entities.keys()
    changes = []
    entities = []
    id_by_name = {}

    for entity in student["entities"]:
        key = normalize(entity["name"])
        id_by_name[key] = entity["id"]
        if key not in reference_entities:
            entities.append({**entity, "status": "removed", "attributes": [
                {**item, "status": "removed"} for item in entity["attributes"]
            ]})
            changes.append(f"«{entity['name']}» obyekti olib tashlandi: shartga ko'ra u kerak emas.")
            continue
        wanted = reference_entities[key]
        wanted_attributes = {normalize(item["name"]): item for item in wanted["attributes"]}
        attributes, added, removed, rekeyed = [], [], [], []
        for item in entity["attributes"]:
            name = normalize(item["name"])
            if item.get("key", "") == "fk":
                attributes.append({**item, "status": "ok"})
            elif name not in wanted_attributes:
                attributes.append({**item, "status": "removed"})
                removed.append(item["name"])
            elif item.get("key", "") != wanted_attributes[name].get("key", ""):
                attributes.append({**item, "key": wanted_attributes[name].get("key", ""), "status": "changed"})
                rekeyed.append(item["name"])
            else:
                attributes.append({**item, "status": "ok"})
        present = {normalize(item["name"]) for item in entity["attributes"]}
        for name, item in wanted_attributes.items():
            if name not in present and item.get("key", "") != "fk":
                attributes.append({**item, "status": "added"})
                added.append(item["name"])
        if added:
            changes.append(f"«{entity['name']}» obyektiga atribut qo'shildi: {', '.join(added)}.")
        if removed:
            changes.append(f"«{entity['name']}» obyektidan ortiqcha atribut olib tashlandi: {', '.join(removed)}.")
        if rekeyed:
            key_names = [item["name"] for item in attributes if item.get("key", "") == "pk" and item["status"] != "removed"]
            changes.append(f"«{entity['name']}» obyektining asosiy kaliti (PK): {', '.join(key_names)}.")
        status = "changed" if added or removed or rekeyed else "ok"
        entities.append({**entity, "attributes": attributes, "status": status})

    right_edge = max((entity["x"] for entity in student["entities"]), default=0) + ADDED_ENTITY_OFFSET_X
    for index, key in enumerate(sorted(reference_entities.keys() - student_entities.keys())):
        wanted = reference_entities[key]
        new_id = f"fix-e{index + 1}"
        id_by_name[key] = new_id
        entities.append(
            {
                "id": new_id,
                "name": wanted["name"],
                "x": right_edge,
                "y": 40 + index * ADDED_ENTITY_STEP_Y,
                "attributes": [{**item, "status": "added"} for item in wanted["attributes"]],
                "status": "added",
            }
        )
        changes.append(f"«{wanted['name']}» obyekti qo'shildi.")

    def display(key):
        entity = student_entities.get(key) or reference_entities[key]
        return entity["name"]

    pairs, missing_relationships, extra_relationships = _match_relationships(
        student_relationships, reference_relationships, common
    )
    pair_by_student = {mine["id"]: wanted for mine, wanted in pairs}
    extra_ids = {item["id"] for item in extra_relationships}
    relationships = []
    for relationship in student_relationships:
        base = {key: relationship[key] for key in ("id", "name", "source", "target", "source_card", "target_card")}
        if relationship["id"] in pair_by_student:
            wanted = pair_by_student[relationship["id"]]
            wanted_cards = _cards_from(wanted, relationship["a"])
            if (relationship["ca"], relationship["cb"]) == wanted_cards:
                relationships.append({**base, "status": "ok"})
            else:
                relationships.append(
                    {**base, "source_card": wanted_cards[0], "target_card": wanted_cards[1], "status": "changed"}
                )
                changes.append(
                    f"«{display(relationship['a'])}» — «{display(relationship['b'])}» bog'lanishining kardinalligi "
                    f"{_card_text(relationship['ca'], relationship['cb'])} dan "
                    f"{_card_text(*wanted_cards)} ga o'zgartirildi."
                )
        else:
            relationships.append({**base, "status": "removed"})
            if relationship["id"] in extra_ids:
                changes.append(
                    f"«{display(relationship['a'])}» va «{display(relationship['b'])}» orasidagi ortiqcha "
                    "bog'lanish olib tashlandi."
                )

    # Yetishmaydigan bog'lanishlar: mavjud obyektlar orasidagilari va yangi qo'shilgan obyektlarnikilari
    added_relationships = missing_relationships + [
        item for item in reference_relationships if not (item["a"] in common and item["b"] in common)
    ]
    for index, wanted in enumerate(added_relationships):
        relationships.append(
            {
                "id": f"fix-r{index + 1}",
                "name": wanted["name"],
                "source": id_by_name[wanted["a"]],
                "target": id_by_name[wanted["b"]],
                "source_card": wanted["ca"],
                "target_card": wanted["cb"],
                "status": "added",
            }
        )
        changes.append(
            f"«{display(wanted['a'])}» va «{display(wanted['b'])}» orasiga bog'lanish qo'shildi "
            f"({_card_text(wanted['ca'], wanted['cb'])}"
            + (f", «{wanted['name']}»" if wanted["name"] else "")
            + ")."
        )
    return {"entities": entities, "relationships": relationships, "changes": changes}


def diagram_to_text(diagram):
    """Diagrammaning AI uchun matnli ko'rinishi."""
    names = {entity["id"]: entity["name"] for entity in diagram["entities"]}
    lines = ["Obyektlar:"]
    for entity in diagram["entities"]:
        attributes = ", ".join(
            item["name"] + (" (PK)" if item.get("key", "") == "pk" else " (FK)" if item.get("key", "") == "fk" else "")
            for item in entity["attributes"]
        )
        lines.append(f"- {entity['name']}: {attributes or '(atributsiz)'}")
    if not diagram["entities"]:
        lines.append("- (yo'q)")
    lines.append("Bog'lanishlar (qavsda shu obyekt tomonidagi kardinallik):")
    for relationship in diagram["relationships"]:
        name = f" — {relationship['name']} —" if relationship["name"] else " —"
        lines.append(
            f"- {names[relationship['source']]} ({relationship['source_card']}){name} "
            f"{names[relationship['target']]} ({relationship['target_card']})"
        )
    if not diagram["relationships"]:
        lines.append("- (yo'q)")
    return "\n".join(lines)
