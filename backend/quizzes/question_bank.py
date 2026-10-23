"""Kirish va chiqish testi uchun savollar: "Ma'lumotlar bazasini loyihalash" fani.

Ikkita parallel variant: A (QUESTIONS) va B (QUESTIONS_B). B ning har bir savoli A dagi o'sha raqamli savolga
juft: mavzu, savol turi, variantlar soni va bilish darajasi bir xil, faqat vaziyat va obyektlar boshqa. Kirish va
chiqish testiga turli variant berilsa, talaba savollarni eslab qolishi (test qilish effekti) o'sishga aralashmaydi;
variantlar ekvivalentligi forms.py da tekshiriladi. Mavzular laboratoriyalar bilan mos:
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


QUESTIONS_B = [
    # --- Konseptual model va ER ---
    single(
        "Konseptual modelni mantiqiy (relyatsion) modeldan nima farqlaydi?",
        "Konseptual model predmet sohasini obyektlar va bog'lanishlar orqali tasvirlaydi, jadval va ustun turlari esa unda bo'lmaydi",
        "Konseptual modelda har bir ustunning ma'lumot turi va uzunligi ko'rsatiladi",
        "Konseptual model faqat PostgreSQL uchun tuziladi",
        "Konseptual modelda indekslar va fayl guruhlari belgilanadi",
        topic="Konseptual model",
    ),
    single(
        "ER-diagrammada «atribut» nimani anglatadi?",
        "Obyektning saqlanadigan xususiyatini (masalan, Kitobning nomi, Talabaning tug'ilgan sanasi)",
        "Ikki obyekt orasidagi bog'lanish turini",
        "Jadvaldagi bitta qatorni",
        "Bazaga ulanish uchun foydalanuvchi nomini",
        topic="Konseptual model",
    ),
    # --- Kalitlar ---
    single(
        "Tarkibli (composite) asosiy kalit nima?",
        "Ikki yoki undan ko'p ustundan iborat kalit: qatorni ustunlar qiymatlari birgalikda yagona aniqlaydi",
        "Har bir ustuni alohida takrorlanmaydigan kalit",
        "Matn va son ustunlaridan avtomatik yaratiladigan indeks",
        "Boshqa jadvalga ishora qiluvchi ustun",
        topic="Kalitlar",
    ),
    single(
        "Tashqi kalit (FOREIGN KEY) cheklovi qaysi xatoning oldini oladi?",
        "Boshqa jadvalda mavjud bo'lmagan qatorga ishora qiluvchi qiymat kiritilishining (masalan, yo'q kitob uchun ijara yozuvi)",
        "Bir ustunga bir xil qiymat ikki marta yozilishining",
        "Jadvalga juda ko'p qator qo'shilishining",
        "Ustunga noto'g'ri ma'lumot turi yozilishining",
        topic="Kalitlar",
    ),
    multiple(
        "«Avtomobil» obyekti uchun qaysi atributlar asosiy kalit bo'la oladi (har biri har bir avtomobilda yagona va doim mavjud)?",
        ["VIN (kuzov raqami)", "Ichki ro'yxat raqami (avtomobil_id)"],
        ["Rangi", "Ishlab chiqarilgan yili"],
        topic="Kalitlar",
    ),
    single(
        "Jadvalda bir nechta nomzod kalit bo'lsa, ulardan biri asosiy kalit qilib tanlanadi. Qolganlari bilan nima qilish to'g'ri?",
        "Ularga UNIQUE (va kerak bo'lsa NOT NULL) cheklovini qo'yish, shunda ham ular takrorlanmaydi",
        "Ularni jadvaldan olib tashlash",
        "Ularga ham PRIMARY KEY qo'yish",
        "Hech narsa qilmaslik: yagonaligi o'z-o'zidan saqlanadi",
        topic="Kalitlar",
    ),
    # --- Bog'lanishlar ---
    single(
        "«Har bir buyurtmani bitta mijoz beradi, bitta mijoz esa ko'p buyurtma bera oladi.» Mijoz va Buyurtma orasidagi bog'lanish turi qanday?",
        "1:N (bir mijoz — ko'p buyurtma)",
        "1:1",
        "M:N",
        "Bog'lanish yo'q",
        topic="Bog'lanishlar",
    ),
    single(
        "Muallif va Kitob orasida 1:N bog'lanish bor (bitta kitobni bitta muallif yozgan). Tashqi kalit qaysi jadvalga qo'yiladi?",
        "Kitob jadvaliga: muallif_id ustuni Muallif jadvalining kalitiga ishora qiladi",
        "Muallif jadvaliga: kitob_id ustuni",
        "Ikkala jadvalga ham bir-biriga ishora qiluvchi ustunlar",
        "Alohida oraliq jadvalga",
        topic="Bog'lanishlar",
    ),
    single(
        "«Shifokor ko'p bemorni qabul qiladi, bemor esa bir nechta shifokorga borishi mumkin.» Bu bog'lanish relyatsion bazada qanday amalga oshiriladi?",
        "Shifokor va Bemor kalitlarini saqlaydigan alohida oraliq jadval (masalan, qabul) yaratiladi",
        "Bemor jadvaliga shifokor_id ustuni qo'shiladi",
        "Shifokor jadvaliga bemor_id ustuni qo'shiladi",
        "Shifokor va Bemor bitta jadvalga birlashtiriladi",
        topic="Bog'lanishlar",
    ),
    single(
        "Talaba va Kurs orasidagi M:N bog'lanish uchun yozilish(talaba_id, kurs_id) oraliq jadvali tuzildi. Uning asosiy kaliti odatda qaysi?",
        "(talaba_id, kurs_id) tarkibli kaliti",
        "Faqat talaba_id",
        "Oraliq jadvalga asosiy kalit kerak emas",
        "Kurs nomi yozilgan matnli ustun",
        topic="Bog'lanishlar",
    ),
    single(
        "«Har bir fuqaroning bittadan pasporti bor, har bir pasport aynan bitta fuqaroga tegishli.» Fuqaro va Pasport orasidagi bog'lanish turi qanday?",
        "1:1",
        "1:N",
        "M:N",
        "N:1",
        topic="Bog'lanishlar",
    ),
    # --- Normallashtirish ---
    single(
        "Normallashtirish qaysi muammoni hal qiladi?",
        "Bir xil faktning bir necha joyda saqlanishi va shu sababli qo'shish, o'zgartirish, o'chirishdagi anomaliyalarni",
        "So'rovlarning sekin ishlashini",
        "Diskdagi bo'sh joy yetishmasligini",
        "Parollarning ochiq saqlanishini",
        topic="Normallashtirish",
    ),
    single(
        "Ikkinchi normal shakl (2NF) ning talabi qaysi?",
        "Jadval 1NF da va kalit bo'lmagan har bir atribut butun kalitga to'liq bog'liq (kalitning bir qismiga emas)",
        "Har bir jadvalda kamida ikkita kalit bo'lishi",
        "Barcha ustunlar matn turida bo'lishi",
        "Jadvalda tashqi kalit bo'lmasligi",
        topic="Normallashtirish",
    ),
    single(
        "Jadval: kitob(id, nom, mualliflar). «mualliflar» ustunida bir nechta ism nuqtali vergul bilan yozilgan. Qaysi normal shakl buzilgan?",
        "1NF",
        "2NF",
        "3NF",
        "Hech biri buzilmagan",
        topic="Normallashtirish",
    ),
    single(
        "Jadval: baho(talaba_id, fan_id, fan_nomi, ball), kaliti — (talaba_id, fan_id). fan_nomi faqat fan_id ga bog'liq. Qaysi normal shakl buzilgan?",
        "2NF (kalitning bir qismiga bog'liqlik)",
        "1NF",
        "Faqat 3NF",
        "Hech biri buzilmagan",
        topic="Normallashtirish",
    ),
    single(
        "Jadval: xodim(id, ism, bolim_id, bolim_telefoni), kaliti — id. bolim_telefoni bolim_id ga bog'liq. Bu qanday bog'liqlik va qaysi normal shaklni buzadi?",
        "Tranzitiv bog'liqlik, 3NF ni buzadi",
        "Qisman bog'liqlik, 2NF ni buzadi",
        "Ko'p qiymatli atribut, 1NF ni buzadi",
        "Hech qanday normal shakl buzilmagan",
        topic="Normallashtirish",
    ),
    single(
        "Normallashtirilmagan jadvalda kurs haqidagi ma'lumot faqat unga yozilgan talabalar qatorlarida saqlanadi. Oxirgi talaba o'chirilganda kurs haqidagi ma'lumot ham yo'qoldi. Bu qanday anomaliya?",
        "O'chirish anomaliyasi",
        "Qo'shish anomaliyasi",
        "Yangilash (o'zgartirish) anomaliyasi",
        "Bu anomaliya emas",
        topic="Normallashtirish",
    ),
    multiple(
        "Qaysi belgilar jadval normallashtirilmaganini ko'rsatadi?",
        [
            "Bitta katakda ro'yxat saqlanadi (masalan, «Toshkent; Samarqand; Buxoro»)",
            "Kalit bo'lmagan ustun qiymati boshqa kalit bo'lmagan ustundan aniqlanadi va qatorlarda takrorlanadi",
        ],
        ["Jadvalda sana turidagi ustun bor", "Jadval nomi ko'plikda yozilgan"],
        topic="Normallashtirish",
    ),
    # --- Cheklovlar va SQL ---
    multiple(
        "Qaysilari ustun yoki jadval darajasidagi cheklovlar (constraint)?",
        ["NOT NULL", "UNIQUE", "CHECK"],
        ["SELECT", "HAVING"],
        topic="Cheklovlar",
    ),
    single(
        "«Talabaning yoshi 16 dan kichik bo'lmasligi kerak» qoidasini bazaning o'zida qaysi cheklov ta'minlaydi?",
        "CHECK (yosh >= 16)",
        "UNIQUE (yosh)",
        "NOT NULL (yosh)",
        "DEFAULT 16",
        topic="Cheklovlar",
    ),
]

FORMS = {"A": QUESTIONS, "B": QUESTIONS_B}


# To'g'ri javob har doim "A" bo'lib qolmasligi uchun variantlar tartibi aralashtiriladi. Urug' (seed) savol
# raqami bo'lgani uchun tartib har safar bir xil: kirish va chiqish testlari ham, hujjat ham mos keladi.
for _questions in FORMS.values():
    for _number, _question in enumerate(_questions, start=1):
        random.Random(_number).shuffle(_question["choices"])
