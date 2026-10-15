"""Platforma ma'lumotlar bazasining ER-diagrammasini Django modellaridan hosil qiladi (Graphviz DOT).

Ishga tushirish (loyiha ildizidan):
    podman compose exec -T backend python manage.py shell < docs/er-diagramma/yaratish.py
Natija backend/er-diagramma-*.dot fayllariga yoziladi, keyin rasmga aylantiriladi:
    dot -Tsvg backend/er-diagramma-fizik.dot -o docs/er-diagramma/fizik.svg   (README.md ga qarang)
"""
from html import escape

from django.apps import apps
from django.db import connection

# Modul -> (sarlavha, rang). Ranglar oq-qora chop etilganda ham farqlanadigan och tonlar.
MODULES = {
    "users": ("Foydalanuvchilar va guruhlar", "#dbeafe"),
    "learning": ("O'quv materiallari va topshiriqlar", "#dcfce7"),
    "submissions": ("Yechimlar, baholash va AI tahlili", "#ffedd5"),
    "grading": ("Yechimlar, baholash va AI tahlili", "#ffedd5"),
    "ai": ("Yechimlar, baholash va AI tahlili", "#ffedd5"),
    "notifications": ("Bildirishnomalar", "#f3f4f6"),
    "labs": ("Virtual laboratoriya", "#ede9fe"),
}
# Django'ning ichki ruxsat tizimi (auth_group, auth_permission) loyiha mavzusiga kirmaydi
SKIP_APPS = {"auth"}

SHORT_TYPES = {
    "timestamp with time zone": "timestamptz",
    "double precision": "float8",
}

# Konseptual diagramma: obyekt nomlari va bog'lanishlar (o'zbekcha)
CONCEPT_NAMES = {
    "users_user": "Foydalanuvchi\n(admin, o'qituvchi, talaba)",
    "users_studentgroup": "Guruh",
    "learning_material": "Material",
    "learning_materialfile": "Material fayli",
    "learning_assignment": "Topshiriq",
    "submissions_submission": "Yechim",
    "ai_aianalysis": "AI tahlili",
    "ai_chatmessage": "Chat xabari",
    "grading_grade": "Baho",
    "notifications_telegramaccount": "Telegram hisobi",
    "notifications_telegramlinkcode": "Telegram bog'lash kodi",
    "notifications_notification": "Bildirishnoma",
    "labs_lab": "Laboratoriya",
    "labs_labattempt": "Laboratoriya urinishi",
    "labs_labgrade": "Laboratoriya bahosi",
}
# (FK egasi, ustun) -> bog'lanish nomi. Ko'rsatilmaganlari ustun nomi bilan yoziladi.
RELATION_LABELS = {
    ("users_user", "group_id"): "a'zo",
    ("learning_material", "author_id"): "yaratadi",
    ("learning_materialfile", "material_id"): "ega",
    ("learning_assignment", "author_id"): "beradi",
    ("submissions_submission", "assignment_id"): "uchun",
    ("submissions_submission", "student_id"): "topshiradi",
    ("ai_aianalysis", "submission_id"): "tahlil qiladi",
    ("ai_chatmessage", "assignment_id"): "haqida",
    ("ai_chatmessage", "student_id"): "yozadi",
    ("grading_grade", "submission_id"): "baholaydi",
    ("grading_grade", "graded_by_id"): "qo'yadi",
    ("notifications_telegramaccount", "user_id"): "bog'langan",
    ("notifications_telegramlinkcode", "user_id"): "uchun",
    ("notifications_notification", "user_id"): "oladi",
    ("notifications_notification", "assignment_id"): "haqida",
    ("labs_lab", "author_id"): "yaratadi",
    ("labs_labattempt", "lab_id"): "uchun",
    ("labs_labattempt", "student_id"): "bajaradi",
    ("labs_labgrade", "lab_id"): "uchun",
    ("labs_labgrade", "student_id"): "oladi",
    ("labs_labgrade", "attempt_id"): "asosida",
}
M2M_LABELS = {
    "users_studentgroup_teachers": "o'qitadi",
    "learning_material_groups": "beriladi",
    "learning_assignment_groups": "beriladi",
    "labs_lab_groups": "beriladi",
}


def column_type(field):
    db_type = field.db_type(connection) or field.get_internal_type()
    return SHORT_TYPES.get(db_type, db_type)


def collect():
    """Jadvallar: nom -> {app, verbose, columns: [(nom, tur, belgilar)]}; bog'lanishlar ro'yxati."""
    tables, relations = {}, []
    for app_label in MODULES:
        for model in apps.get_app_config(app_label).get_models():
            meta = model._meta
            columns = []
            for field in meta.local_fields:
                marks = []
                if field.primary_key:
                    marks.append("PK")
                if field.is_relation:
                    marks.append("FK")
                if field.unique and not field.primary_key:
                    marks.append("UQ")
                if field.null:
                    marks.append("NULL")
                columns.append((field.column, column_type(field), marks))
                if field.is_relation:
                    relations.append(
                        {
                            "from": meta.db_table,
                            "column": field.column,
                            "to": field.related_model._meta.db_table,
                            "one_to_one": field.one_to_one,
                            "optional": field.null,
                        }
                    )
            tables[meta.db_table] = {"app": app_label, "verbose": str(meta.verbose_name), "columns": columns}
            for m2m in meta.local_many_to_many:
                if m2m.related_model._meta.app_label in SKIP_APPS:
                    continue
                through = m2m.remote_field.through._meta
                target = m2m.related_model._meta.db_table
                through_columns = [("id", "bigint", ["PK"])]
                for field in through.local_fields:
                    if field.is_relation:
                        through_columns.append((field.column, column_type(field), ["FK"]))
                        relations.append(
                            {
                                "from": through.db_table,
                                "column": field.column,
                                "to": field.related_model._meta.db_table,
                                "one_to_one": False,
                                "optional": False,
                            }
                        )
                tables[through.db_table] = {
                    "app": app_label,
                    "verbose": f"oraliq jadval: {meta.verbose_name} ↔ {m2m.related_model._meta.verbose_name}",
                    "columns": through_columns,
                    "through": (meta.db_table, target),
                }
    return tables, relations


def physical_dot(tables, relations):
    lines = [
        "digraph ER {",
        '  graph [rankdir=LR, splines=true, nodesep=0.35, ranksep=1.1, fontname="DejaVu Sans", '
        'fontsize=20, label="Platforma ma\'lumotlar bazasining fizik modeli", labelloc=t, pad=0.4];',
        '  node [shape=plain, fontname="DejaVu Sans", fontsize=10];',
        '  edge [fontname="DejaVu Sans", fontsize=9, color="#475569", dir=both, arrowsize=0.9];',
    ]
    clusters = {}
    for name, table in tables.items():
        clusters.setdefault(MODULES[table["app"]][0], []).append(name)
    for index, (title, names) in enumerate(clusters.items()):
        color = MODULES[tables[names[0]]["app"]][1]
        lines.append(f"  subgraph cluster_{index} {{")
        lines.append(f'    label="{title}"; style="rounded,filled"; color="#cbd5e1"; fillcolor="{color}55"; fontsize=13;')
        for name in names:
            table = tables[name]
            rows = [
                f'<tr><td colspan="3" bgcolor="{color}"><b>{escape(name)}</b><br/>'
                f'<font point-size="9">{escape(table["verbose"])}</font></td></tr>'
            ]
            for column, kind, marks in table["columns"]:
                key = ", ".join(mark for mark in marks if mark in ("PK", "FK", "UQ"))
                column_text = f"<u>{escape(column)}</u>" if "PK" in marks else escape(column)
                if "NULL" in marks:
                    column_text += ' <font color="#64748b">(null)</font>'
                key_text = f"<b>{key}</b>" if key else " "
                rows.append(
                    f'<tr><td align="left" port="{escape(column)}">{key_text}</td>'
                    f'<td align="left">{column_text}</td>'
                    f'<td align="left"><font color="#475569">{escape(kind)}</font></td></tr>'
                )
            label = '<table border="0" cellborder="1" cellspacing="0" cellpadding="3" bgcolor="white">' + "".join(rows) + "</table>"
            lines.append(f'    "{name}" [label=<{label}>];')
        lines.append("  }")
    for relation in relations:
        # Crow's foot: FK egasi tomoni — "ko'p" (yoki 1:1 da "bitta"), havola qilingan tomon — "bitta"
        tail = "teetee" if relation["one_to_one"] else "crowodot"
        head = "teeodot" if relation["optional"] else "teetee"
        lines.append(
            f'  "{relation["from"]}":"{relation["column"]}" -> "{relation["to"]}":"id" '
            f"[arrowtail={tail}, arrowhead={head}];"
        )
    lines.append("}")
    return "\n".join(lines)


def conceptual_dot(tables, relations):
    lines = [
        "graph ER {",
        '  graph [layout=neato, overlap=false, sep="+18", splines=true, fontname="DejaVu Sans", fontsize=20, '
        'label="Platforma ma\'lumotlar bazasining konseptual modeli (ER-diagramma)", labelloc=t, pad=0.4];',
        '  node [fontname="DejaVu Sans", fontsize=12];',
        '  edge [fontname="DejaVu Sans", fontsize=10, color="#475569"];',
    ]
    for name, title in CONCEPT_NAMES.items():
        color = MODULES[tables[name]["app"]][1]
        label = title.replace("\n", "\\n")
        lines.append(f'  "{name}" [shape=box, style="rounded,filled", fillcolor="{color}", label="{label}"];')

    def relationship(index, label, left, right, left_card, right_card):
        diamond = f"r{index}"
        lines.append(f'  {diamond} [shape=diamond, style=filled, fillcolor="#fef9c3", fontsize=10, label="{label}"];')
        lines.append(f'  "{left}" -- {diamond} [taillabel="{left_card}", labeldistance=1.6];')
        lines.append(f'  {diamond} -- "{right}" [headlabel="{right_card}", labeldistance=1.6];')

    index = 0
    for relation in relations:
        source, target = relation["from"], relation["to"]
        if source in CONCEPT_NAMES:
            index += 1
            label = RELATION_LABELS.get((source, relation["column"]), relation["column"])
            many = "1" if relation["one_to_one"] else "N"
            one = "0..1" if relation["optional"] else "1"
            relationship(index, label, target, source, one, many)
    for name, table in tables.items():
        if "through" in table:
            index += 1
            left, right = table["through"]
            relationship(index, M2M_LABELS.get(name, "bog'liq"), left, right, "M", "N")
    lines.append("}")
    return "\n".join(lines)


TABLES, RELATIONS = collect()
with open("er-diagramma-fizik.dot", "w", encoding="utf-8") as output:
    output.write(physical_dot(TABLES, RELATIONS))
with open("er-diagramma-konseptual.dot", "w", encoding="utf-8") as output:
    output.write(conceptual_dot(TABLES, RELATIONS))
print(f"Jadvallar: {len(TABLES)}, bog'lanishlar: {len(RELATIONS)}")
