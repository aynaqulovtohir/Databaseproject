"""Kirish va chiqish testi uchun savollar: "Ma'lumotlar bazasini loyihalash" fani.

Tajriba uchun kirish va chiqish testlari bir xil savollardan tuziladi: shunda o'sishni
to'g'ridan-to'g'ri solishtirish mumkin. Mavzular laboratoriyalar bilan mos:
konseptual model va ER, kalitlar, bog'lanishlar, normallashtirish, cheklovlar.

Bazaga qo'shish: python manage.py seed_entry_test --author <login> --group <guruh>
"""
import random

TEST_TITLE = "Ma'lumotlar bazasini loyihalash"
TEST_DESCRIPTION = (
    "Test ma'lumotlar bazasini loyihalash bo'yicha bilimingizni o'lchaydi: ER-model, kalitlar, bog'lanishlar, "
    "normallashtirish va cheklovlar. Bilmagan savolingizni taxmin qilmasdan o'tkazib yuborishingiz mumkin. "
    "Natija bahoga ta'sir qilmaydi."
)


def single(text, correct, *wrong, topic):
    """Bitta to'g'ri javobli savol: birinchi argument to'g'ri javob (tartib keyin aralashtiriladi)."""
    return {
        "topic": topic,
        "text": text,
        "kind": "single",
        "points": 1,
        "choices": [{"text": correct, "is_correct": True}] + [{"text": item, "is_correct": False} for item in wrong],
    }


def multiple(text, correct, wrong, topic):
    """Bir nechta to'g'ri javobli savol."""
    return {
        "topic": topic,
        "text": text,
        "kind": "multiple",
        "points": 1,
        "choices": [{"text": item, "is_correct": True} for item in correct]
        + [{"text": item, "is_correct": False} for item in wrong],
    }


QUESTIONS = [
    # --- Konseptual model va ER ---
    single(
        "Ma'lumotlar bazasini loyihalashda konseptual model nimani tasvirlaydi?",
        "Predmet sohasidagi obyektlar, ularning atributlari va bog'lanishlarini, aniq MBBTga bog'lanmagan holda",
        "Jadvallar, ustunlarning ma'lumot turlari va indekslarni",
        "Ma'lumotlar diskda qanday saqlanishini",
        "SQL so'rovlarining bajarilish rejasini",
        topic="Konseptual model",
    ),
    single(
        "ER-diagrammada «obyekt» (entity) nimani anglatadi?",
        "Ma'lumoti saqlanadigan real yoki mavhum narsani (masalan, Talaba, Kitob)",
        "Jadvaldagi bitta ustunni",
        "Ikki jadval orasidagi bog'lanishni",
        "SQL buyrug'ini",
        topic="Konseptual model",
    ),
    # --- Kalitlar ---
    single(
        "Asosiy kalit (PRIMARY KEY) qanday talabga javob berishi kerak?",
        "Qiymatlari takrorlanmaydi va bo'sh (NULL) bo'lmaydi",
        "Qiymatlari takrorlanishi mumkin, lekin bo'sh bo'lmaydi",
        "Faqat matn turidagi ustun bo'ladi",
        "Har doim jadvalning birinchi ustuni bo'ladi",
        topic="Kalitlar",
    ),
    single(
        "Tashqi kalit (FOREIGN KEY) nima uchun ishlatiladi?",
        "Jadvaldagi qiymat boshqa jadvaldagi mavjud qatorga ishora qilishini ta'minlash uchun",
        "Jadvaldagi qatorlarni tartiblash uchun",
        "Qidiruvni tezlashtirish uchun",
        "Maxfiy ma'lumotlarni shifrlash uchun",
        topic="Kalitlar",
    ),
    multiple(
        "«Talaba» obyekti uchun qaysi atributlar asosiy kalit bo'la oladi (har biri har bir talabada yagona va doim mavjud)?",
        ["Talaba ID raqami", "Pasport seriyasi va raqami"],
        ["Ism", "Tug'ilgan sana"],
        topic="Kalitlar",
    ),
    single(
        "PostgreSQL'da UNIQUE cheklovi PRIMARY KEY dan nimasi bilan farq qiladi?",
        "UNIQUE ustunda bo'sh (NULL) qiymat bo'lishi mumkin va jadvalda bir nechta UNIQUE bo'la oladi; PRIMARY KEY esa bitta va NULL bo'lmaydi",
        "Hech qanday farqi yo'q",
        "UNIQUE faqat son turidagi ustunlarga qo'yiladi",
        "PRIMARY KEY qiymatlari takrorlanishi mumkin, UNIQUE niki esa yo'q",
        topic="Kalitlar",
    ),
    # --- Bog'lanishlar ---
    single(
        "«Har bir talaba bitta guruhda o'qiydi, bitta guruhda esa ko'p talaba bor.» Guruh va Talaba orasidagi bog'lanish turi qanday?",
        "1:N (bir guruh — ko'p talaba)",
        "1:1",
        "M:N",
        "Bog'lanish yo'q",
        topic="Bog'lanishlar",
    ),
    single(
        "1:N bog'lanish relyatsion bazada qanday ifodalanadi?",
        "«Ko'p» tomondagi jadvalga «bir» tomondagi jadvalning kalitiga ishora qiluvchi tashqi kalit qo'shiladi",
        "«Bir» tomondagi jadvalga «ko'p» tomondagi jadvalning kaliti qo'shiladi",
        "Ikkala jadval bitta jadvalga birlashtiriladi",
        "Faqat bog'lanish nomi yoziladi, kalit kerak emas",
        topic="Bog'lanishlar",
    ),
    single(
        "«Talaba bir nechta fanni o'qiydi, bitta fanni esa ko'p talaba o'qiydi.» Bu bog'lanish relyatsion bazada qanday amalga oshiriladi?",
        "Talaba va Fan kalitlarini saqlaydigan alohida oraliq jadval yaratiladi",
        "Talaba jadvaliga fan_id ustuni qo'shiladi",
        "Fan jadvaliga talaba_id ustuni qo'shiladi",
        "Talaba va Fan bitta jadvalga birlashtiriladi",
        topic="Bog'lanishlar",
    ),
    single(
        "M:N bog'lanish uchun yaratilgan oraliq jadvalning asosiy kaliti odatda nima bo'ladi?",
        "Ikki tashqi kalitdan iborat tarkibli kalit",
        "Birinchi jadvalning asosiy kaliti",
        "Oraliq jadvalga asosiy kalit kerak emas",
        "Bog'lanish nomi yozilgan matnli ustun",
        topic="Bog'lanishlar",
    ),
    single(
        "«Har bir bo'limni aynan bitta mudir boshqaradi, bitta xodim esa faqat bitta bo'limni boshqara oladi.» Bo'lim va Mudir orasidagi bog'lanish turi qanday?",
        "1:1",
        "1:N",
        "M:N",
        "N:1",
        topic="Bog'lanishlar",
    ),
    # --- Normallashtirish ---
    single(
        "Normallashtirishning asosiy maqsadi nima?",
        "Ma'lumotlar takrorlanishini va o'zgartirishdagi anomaliyalarni kamaytirish",
        "Har qanday so'rovni tezlashtirish",
        "Jadvallar sonini imkon qadar kamaytirish",
        "Barcha ustunlarni bir xil ma'lumot turiga keltirish",
        topic="Normallashtirish",
    ),
    single(
        "Birinchi normal shakl (1NF) ning talabi qaysi?",
        "Har bir katakda faqat bitta, bo'linmas qiymat bo'lishi",
        "Har bir jadvalda tashqi kalit bo'lishi",
        "Har bir jadvalda kamida uchta ustun bo'lishi",
        "Kalit bo'lmagan atributlar bir-biriga bog'liq bo'lmasligi",
        topic="Normallashtirish",
    ),
    single(
        "Jadval: talaba(id, ism, telefonlar). «telefonlar» ustunida bir nechta raqam vergul bilan yozilgan. Qaysi normal shakl buzilgan?",
        "1NF",
        "2NF",
        "3NF",
        "Hech biri buzilmagan",
        topic="Normallashtirish",
    ),
    single(
        "Jadval: buyurtma_tarkibi(buyurtma_id, mahsulot_kodi, mahsulot_nomi, soni), kaliti — (buyurtma_id, mahsulot_kodi). "
        "mahsulot_nomi faqat mahsulot_kodi ga bog'liq. Qaysi normal shakl buzilgan?",
        "2NF (kalitning bir qismiga bog'liqlik)",
        "1NF",
        "Faqat 3NF",
        "Hech biri buzilmagan",
        topic="Normallashtirish",
    ),
    single(
        "Jadval: talaba(id, ism, guruh_id, guruh_nomi), kaliti — id. guruh_nomi guruh_id ga bog'liq. Bu qanday bog'liqlik va qaysi normal shaklni buzadi?",
        "Tranzitiv bog'liqlik, 3NF ni buzadi",
        "Qisman bog'liqlik, 2NF ni buzadi",
        "Ko'p qiymatli atribut, 1NF ni buzadi",
        "Hech qanday normal shakl buzilmagan",
        topic="Normallashtirish",
    ),
    single(
        "Normallashtirilmagan jadvalda mijoz telefonini o'zgartirish uchun bir nechta qatorni yangilash kerak, bittasi esa e'tibordan chetda qoldi. Bu qanday anomaliya?",
        "Yangilash (o'zgartirish) anomaliyasi",
        "Qo'shish anomaliyasi",
        "O'chirish anomaliyasi",
        "Bu anomaliya emas",
        topic="Normallashtirish",
    ),
    multiple(
        "Qaysi holatlarda ma'lumotni alohida jadvalga (obyektga) ajratish kerak?",
        [
            "Atribut bir nechta qiymatga ega bo'lsa (masalan, talabaning bir nechta telefoni)",
            "Bir xil ma'lumot ko'p qatorlarda takrorlansa (masalan, har bir buyurtmada mijoz ismi)",
        ],
        ["Jadvalda beshtadan ortiq ustun bo'lsa", "Ustun nomi uzun bo'lsa"],
        topic="Normallashtirish",
    ),
    # --- Cheklovlar va SQL ---
    multiple(
        "Qaysilari ma'lumotlar yaxlitligini ta'minlovchi cheklovlar (constraint)?",
        ["PRIMARY KEY", "FOREIGN KEY", "CHECK"],
        ["ORDER BY", "GROUP BY"],
        topic="Cheklovlar",
    ),
    single(
        "«Mahsulot narxi manfiy bo'lmasligi kerak» qoidasini bazaning o'zida qaysi cheklov ta'minlaydi?",
        "CHECK (narx >= 0)",
        "UNIQUE (narx)",
        "PRIMARY KEY (narx)",
        "DEFAULT 0",
        topic="Cheklovlar",
    ),
]


# To'g'ri javob har doim "A" bo'lib qolmasligi uchun variantlar tartibi aralashtiriladi. Urug' (seed) savol
# raqami bo'lgani uchun tartib har safar bir xil: kirish va chiqish testlari ham, hujjat ham mos keladi.
for _number, _question in enumerate(QUESTIONS, start=1):
    random.Random(_number).shuffle(_question["choices"])
