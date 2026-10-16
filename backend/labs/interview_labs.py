"""Talablarni aniqlash laboratoriyalari: shartda faqat vaziyat, talablarni talaba AI-buyurtmachidan so'rab oladi.

Talablar (requirements) namunaviy diagramma bilan mos bo'lishi shart: diagrammadagi har bir obyekt, atribut va
bog'lanish kamida bitta talabda aytilgan. Atribut nomlari talab matnida diagrammadagidek yoziladi — buyurtmachi
ularni shunday aytadi va talaba diagrammada shunday yozadi (tekshiruv nomlar bo'yicha solishtiradi).
"""

INTERVIEW_NOTE = """\
Diagrammani chizish qoidalari:
- Obyekt va atribut nomlarini buyurtmachi aytgan (yoki talablarda yozilgan) so'zlar bilan yozing (katta-kichik harf \
farqi yo'q).
- Har bir obyektda asosiy kalitni (PK) belgilang; tashqi kalitlarni (FK) yozish shart emas.
- Har bir bog'lanishning ikki uchida kardinallikni tanlang: «1» yoki «N»."""


def _entity(entity_id, name, x, y, key, *attributes):
    return {
        "id": entity_id,
        "name": name,
        "x": x,
        "y": y,
        "attributes": [{"name": key, "key": "pk"}] + [{"name": item, "key": ""} for item in attributes],
    }


def _relationship(relationship_id, name, source, source_card, target, target_card):
    return {"id": relationship_id, "name": name, "source": source, "target": target, "source_card": source_card, "target_card": target_card}


THEORY = """\
Talablarni aniqlash — loyihalashning birinchi bosqichi: buyurtmachi bazani qanday tasavvur qilishini emas, \
uning ishida nimalar sodir bo'lishini bilib olasiz. Buyurtmachi texnik atamalarni bilmaydi va o'zi hamma narsani \
aytmaydi: kerakli ma'lumotni savollar bilan olasiz.

Savollarni tartib bilan bering:
1. Kimlar va nimalar? — «Ishingizda kimlar qatnashadi? Nimalar hisobga olinadi?» (obyektlar)
2. Ular haqida nima yoziladi? — «Mijoz haqida qaysi ma'lumotlarni saqlaysiz? Har birini qanday ajratasiz?» \
(atributlar va kalit)
3. Ular qanday bog'langan? — har bir juftlik uchun ikki yo'nalishda so'rang: «Bitta mijoz nechta buyurtma beradi? \
Bitta buyurtma nechta mijozga tegishli?» (kardinallik)
4. Qanday qoidalar bor? — «Qaysi ma'lumot majburiy? Nima keyinroq to'ldiriladi?» (biznes qoidalari)

Yaxshi savol aniq bo'ladi: «Hammasini ayting» emas, «Buyurtma haqida nimalar yoziladi?». Javobni o'z so'zlaringiz \
bilan qaytarib tekshiring: «Demak, bitta buyurtmani faqat bitta kuryer yetkazadi, to'g'rimi?».

Namuna (boshqa soha: do'kon):
- Talaba: «Do'koningizda nimalar hisobga olinadi?» — Buyurtmachi: «Mahsulotlar va sotuvlar.»
- Talaba: «Bitta sotuvda nechta mahsulot bo'lishi mumkin? Bitta mahsulot-chi?» — Buyurtmachi: «Bitta sotuvda bir \
nechta mahsulot, bitta mahsulot esa ko'p marta sotiladi.» → Sotuv N — N Mahsulot."""

INTERVIEW_LABS = [
    {
        "kind": "er",
        "title": "Talablarni aniqlash 1. Poliklinika",
        "description": f"""\
«Shifo» xususiy poliklinikasi qog'oz jurnallar o'rniga elektron baza xohlaydi. Buyurtmachi — poliklinikaning \
bosh shifokori. Bazada nimalar saqlanishi kerakligini aniqlang va konseptual ER-diagramma chizing.

{INTERVIEW_NOTE}""",
        "theory": THEORY,
        "client_persona": (
            "Siz «Shifo» xususiy poliklinikasining bosh shifokori Dilnoza Karimovasiz. Poliklinikani yaxshi bilasiz, "
            "lekin dasturlash va ma'lumotlar bazasidan uzoqsiz. Xushmuomala, qisqa gapirasiz."
        ),
        "requirements": [
            {"id": "R1", "kind": "entity", "text": "Poliklinikaga murojaat qiladigan bemorlar ro'yxatini yuritamiz (hujjatlarda «Bemor»)."},
            {"id": "R2", "kind": "attribute", "text": "Har bir bemorga alohida raqam beramiz (id). Bemor haqida yoziladi: ism, familiya, tugilgan_sana, telefon."},
            {"id": "R3", "kind": "entity", "text": "Poliklinikada shifokorlar ishlaydi (hujjatlarda «Shifokor»)."},
            {"id": "R4", "kind": "attribute", "text": "Har bir shifokorning raqami (id) bor. Shifokor haqida yoziladi: ism, familiya, mutaxassislik (masalan, kardiolog)."},
            {"id": "R5", "kind": "entity", "text": "Poliklinika bo'limlarga bo'lingan (hujjatlarda «Bolim» deb yoziladi, masalan, terapiya bo'limi)."},
            {"id": "R6", "kind": "attribute", "text": "Har bir bo'limning raqami (id) bor. Bo'lim haqida yoziladi: nomi va qavat (qaysi qavatda joylashgani)."},
            {"id": "R7", "kind": "relationship", "text": "Har bir shifokor faqat bitta bo'limda ishlaydi, bitta bo'limda esa bir nechta shifokor ishlaydi."},
            {"id": "R8", "kind": "entity", "text": "Bemor shifokor qabuliga yoziladi va har bir qabul alohida qayd etiladi (hujjatlarda «Qabul»)."},
            {"id": "R9", "kind": "attribute", "text": "Har bir qabulning raqami (id) bor. Qabul haqida yoziladi: sana, vaqt va shifokor qo'ygan tashxis."},
            {"id": "R10", "kind": "relationship", "text": "Har bir qabul bitta bemorga tegishli; bitta bemor ko'p marta qabulga kelishi mumkin."},
            {"id": "R11", "kind": "relationship", "text": "Har bir qabulni bitta shifokor o'tkazadi; bitta shifokor ko'p qabul o'tkazadi."},
            {"id": "R12", "kind": "rule", "text": "Tashxis qabuldan keyin yoziladi, shuning uchun yangi yozilgan qabulda tashxis hali bo'sh bo'ladi."},
        ],
        "reference_diagram": {
            "entities": [
                _entity("bemor", "Bemor", 40, 40, "id", "ism", "familiya", "tugilgan_sana", "telefon"),
                _entity("qabul", "Qabul", 380, 160, "id", "sana", "vaqt", "tashxis"),
                _entity("shifokor", "Shifokor", 720, 40, "id", "ism", "familiya", "mutaxassislik"),
                _entity("bolim", "Bolim", 720, 320, "id", "nomi", "qavat"),
            ],
            "relationships": [
                _relationship("r1", "yoziladi", "qabul", "N", "bemor", "1"),
                _relationship("r2", "o'tkazadi", "qabul", "N", "shifokor", "1"),
                _relationship("r3", "ishlaydi", "shifokor", "N", "bolim", "1"),
            ],
        },
    },
]
