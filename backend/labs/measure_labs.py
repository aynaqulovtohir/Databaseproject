"""Pilot tadqiqot uchun AI'siz o'lchov topshiriqlari (Qo'shimcha material, S1).

Uchta vaziyat izomorf: har birida 4 ta obyekt va 11 ta atribut, bitta ko'p-ko'p (M:N) bog'lanish va ikkita 1:N
bog'lanish bilan ulangan bitta hodisa obyekti bor (andoza — mashq laboratoriyasi «ER-model 2. Kutubxona»). Shu tufayli
kirish, chiqish va kechiktirilgan bosqichlar orasidagi farq vaziyat qiyinligiga emas, talaba kompetentligiga bog'liq.
Vaziyatlar bosqichlar bo'yicha guruhlarda almashlab beriladi (masalan, A → B → C, B → C → A, C → A → B).

Bu topshiriqlar mashq ro'yxatiga (design_labs.ALL_LABS) ataylab kiritilmagan: talaba ularni o'lchovdan oldin ko'rmasligi
kerak. Bazaga qo'shish: python manage.py seed_measure_labs --author <login> --group <guruh> [--module <id>]
Topshirishda yozma asoslash so'raladi (rubrikaning «qarorlarni asoslash» mezoni).
"""
from .design_labs import ER_NOTE, _entity, _relationship

JUSTIFICATION_NOTE = """\
Topshirishda 2–3 gap bilan yozing: qaysi tushunchani alohida obyekt qildingiz va nega? Ko'p-ko'p bog'lanishni \
qanday ifodaladingiz?"""


def _description(place, entities, rules):
    lines = [f"{place} uchun konseptual ER-diagramma chizing.", "", "Obyektlar va ularning atributlari:"]
    lines += [f"- {name}: {', '.join(attributes)}" for name, attributes in entities]
    lines += ["", "Biznes qoidalari:"] + [f"- {rule}" for rule in rules]
    lines += ["", "O'zingiz aniqlaysiz: bog'lanishlar, ularning kardinalligi va har bir obyektning asosiy kaliti.", "",
              ER_NOTE, "", JUSTIFICATION_NOTE]
    return "\n".join(lines)


def _lab(code, place, entities, rules, relationships):
    return {
        "kind": "er",
        "title": f"O'lchov ER-{code}. {place}",
        "description": _description(place, entities, rules),
        "ask_justification": True,
        "reference_diagram": {
            "entities": [
                _entity(name.lower().replace("'", ""), name, x, y, *attributes)
                for (name, attributes), (x, y) in zip(entities, [(40, 40), (440, 40), (440, 320), (40, 320)])
            ],
            "relationships": [_relationship(f"r{i}", *rel) for i, rel in enumerate(relationships, start=1)],
        },
    }


MEASURE_LABS = [
    _lab(
        "A", "Mehmonxona",
        [("Xona", ["raqam", "turi", "narxi"]), ("Qulaylik", ["id", "nomi"]),
         ("Mehmon", ["id", "ism", "pasport"]), ("Bron", ["id", "kelish_sana", "ketish_sana"])],
        ["Har bir xona o'z raqami bilan aniqlanadi.",
         "Bitta xonada bir nechta qulaylik (masalan, konditsioner, balkon) bo'lishi, bitta qulaylik esa ko'p xonada "
         "bo'lishi mumkin.",
         "Mehmon xonani bron qiladi. Har bir bron yozuvi aynan bitta xona va aynan bitta mehmonga tegishli; bitta "
         "xona va bitta mehmonning ko'p broni bo'lishi mumkin."],
        [("mavjud", "qulaylik", "N", "xona", "N"), ("bron qilinadi", "xona", "1", "bron", "N"),
         ("bron qiladi", "mehmon", "1", "bron", "N")],
    ),
    _lab(
        "B", "Kinoteatr",
        [("Film", ["id", "nomi", "yil"]), ("Aktyor", ["id", "ism"]),
         ("Tomoshabin", ["id", "ism", "telefon"]), ("Chipta", ["id", "seans_vaqti", "orindiq"])],
        ["Har bir film o'z identifikatori bilan aniqlanadi.",
         "Bitta filmda bir nechta aktyor o'ynashi, bitta aktyor esa ko'p filmda o'ynashi mumkin.",
         "Tomoshabin filmga chipta sotib oladi. Har bir chipta aynan bitta film va aynan bitta tomoshabinga tegishli; "
         "bitta film va bitta tomoshabinning ko'p chiptasi bo'lishi mumkin."],
        [("o'ynagan", "aktyor", "N", "film", "N"), ("chipta sotiladi", "film", "1", "chipta", "N"),
         ("sotib oladi", "tomoshabin", "1", "chipta", "N")],
    ),
    _lab(
        "C", "Onlayn kurslar",
        [("Kurs", ["id", "nomi", "soat"]), ("Oqituvchi", ["id", "ism"]),
         ("Tinglovchi", ["id", "ism", "email"]), ("Yozilish", ["id", "sana", "baho"])],
        ["Har bir kurs o'z identifikatori bilan aniqlanadi.",
         "Bitta kursni bir nechta o'qituvchi birga o'qitishi, bitta o'qituvchi esa ko'p kursni o'qitishi mumkin.",
         "Tinglovchi kursga yoziladi. Har bir yozilish yozuvi aynan bitta kurs va aynan bitta tinglovchiga tegishli; "
         "bitta kurs va bitta tinglovchining ko'p yozilishi bo'lishi mumkin (masalan, kursni qayta o'qish)."],
        [("o'qitadi", "oqituvchi", "N", "kurs", "N"), ("yozuvlari", "kurs", "1", "yozilish", "N"),
         ("yoziladi", "tinglovchi", "1", "yozilish", "N")],
    ),
]
