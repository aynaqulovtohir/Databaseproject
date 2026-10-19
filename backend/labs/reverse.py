"""Teskari loyihalash: tayyor bazadan (jadvallar va kalitlar) namunaviy ER-diagrammani hosil qilish.

ER laboratoriyasida setup_sql berilsa, talaba shu bazaning ER-diagrammasini tiklaydi. O'qituvchi namunani chizmaydi:
setup_sql qum qutida bajariladi va jadvallar tuzilishidan diagramma quriladi:
- har bir jadval — obyekt, ustunlar — atributlar (asosiy kalit — "pk", tashqi kalit — "fk": solishtirishda fk
  atributlar hisobga olinmaydi, ularni bog'lanish ifodalaydi);
- FOREIGN KEY — bog'lanish: jadval tomonida N, havola qilingan jadval tomonida 1; FK ustunlari UNIQUE yoki asosiy
  kalit bo'lsa — 1:1;
- faqat ikkita tashqi kalitdan iborat oraliq jadval (asosiy kaliti ham shu ikki ustun) — M:N bog'lanish, jadval nomi
  bilan. Qo'shimcha ustuni bor oraliq jadval (masalan, baho) obyekt bo'lib qoladi.
"""
import re

from .er import validate_diagram
from .sandbox import run_sql

COLUMNS = re.compile(r"\(([^)]*)\)")
FOREIGN_KEY = re.compile(r"^FOREIGN KEY \(([^)]*)\) REFERENCES ([^\s(]+)\s*\(([^)]*)\)", re.IGNORECASE)
GRID_COLUMNS = 3
STEP_X, STEP_Y = 300, 240


class ReverseError(ValueError):
    """Bazadan diagramma hosil qilib bo'lmadi (o'qituvchiga ko'rsatiladigan xabar bilan)."""


def _names(text):
    return [item.strip().strip('"') for item in text.split(",") if item.strip()]


def _keys(state):
    """(asosiy kalit ustunlari, UNIQUE ustunlar to'plamlari, [(fk ustunlari, havola jadvali)])."""
    primary, unique, foreign = [], [], []
    for definition in state.constraints:
        upper = definition.upper()
        if upper.startswith("PRIMARY KEY"):
            primary = _names(COLUMNS.search(definition).group(1))
        elif upper.startswith("UNIQUE"):
            unique.append(set(_names(COLUMNS.search(definition).group(1))))
        elif upper.startswith("FOREIGN KEY"):
            match = FOREIGN_KEY.match(definition)
            if match:
                foreign.append((_names(match.group(1)), match.group(2).strip('"')))
    return primary, unique, foreign


def schema_to_diagram(tables):
    """sandbox.TableState lug'atidan ER-diagramma (er.py formatida, validate_diagram dan o'tgan)."""
    if not tables:
        raise ReverseError("Berilgan bazada birorta jadval yo'q.")
    keys = {name: _keys(state) for name, state in tables.items()}

    junctions = {}
    for name, (primary, _, foreign) in keys.items():
        columns = set(tables[name].columns)
        fk_columns = [column for columns_, _ in foreign for column in columns_]
        if (
            len(foreign) == 2
            and all(len(columns_) == 1 for columns_, _ in foreign)
            and set(fk_columns) == columns == set(primary)
            and foreign[0][1] != foreign[1][1]
        ):
            # Uchlar jadvaldagi ustunlar tartibida (cheklovlar alifbo bo'yicha keladi)
            order = list(tables[name].columns)
            first, second = sorted(foreign, key=lambda item: order.index(item[0][0]))
            junctions[name] = (first[1], second[1])

    entities, positions = [], {}
    for index, name in enumerate(sorted(name for name in tables if name not in junctions)):
        primary, _, foreign = keys[name]
        fk_columns = {column for columns_, _ in foreign for column in columns_}
        attributes = [
            {"name": column, "key": "pk" if column in primary else ("fk" if column in fk_columns else "")}
            for column in tables[name].columns
        ]
        positions[name] = f"e{index + 1}"
        entities.append(
            {
                "id": positions[name],
                "name": name,
                "x": 40 + (index % GRID_COLUMNS) * STEP_X,
                "y": 40 + (index // GRID_COLUMNS) * STEP_Y,
                "attributes": attributes,
            }
        )

    relationships = []
    for name in sorted(tables):
        if name in junctions:
            first, second = junctions[name]
            relationships.append(
                {"source": positions[first], "target": positions[second], "source_card": "N", "target_card": "N",
                 "name": name}
            )
            continue
        primary, unique, foreign = keys[name]
        for columns_, target in foreign:
            if target not in positions:
                raise ReverseError(f"«{name}» jadvalidagi tashqi kalit «{target}» jadvaliga havola qiladi, u esa oraliq jadval.")
            one_to_one = set(columns_) in unique or set(columns_) == set(primary)
            relationships.append(
                {"source": positions[name], "target": positions[target], "source_card": "1" if one_to_one else "N",
                 "target_card": "1", "name": ""}
            )
    for index, relationship in enumerate(relationships, start=1):
        relationship["id"] = f"r{index}"
    return validate_diagram({"entities": entities, "relationships": relationships})


def diagram_from_sql(setup_sql):
    """setup_sql ni qum qutida bajarib, ER-diagramma qaytaradi. SQL xatosi — checker.LabSetupError."""
    from .checker import LabSetupError

    outcome = run_sql("SELECT 1", setup_sql)
    if outcome.error:
        raise LabSetupError("setup_sql", outcome.error)
    return schema_to_diagram(outcome.tables)
