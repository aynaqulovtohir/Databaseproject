"""Ma'lumotlar bazasini loyihalash bo'yicha tayyor laboratoriyalar to'plami.

Tekshiruv talaba yaratgan jadvallarni namunaviy yechim bilan solishtiradi: jadval va
ustun nomlari, turlari, NOT NULL, kalitlar va cheklovlar, jadvallardagi ma'lumotlar.
Shuning uchun shartda nomlar va turlar aniq beriladi, loyihalash qarorlari esa
(asosiy va tashqi kalitlar, NOT NULL, UNIQUE, ma'lumotni ko'chirish) talabaning o'ziga qoladi.

Laboratoriyalarni bazaga qo'shish: python manage.py seed_design_labs --author <login> --group <guruh>
"""

from .er_sql_labs import ER_SQL_LABS
from .index_labs import INDEX_LABS
from .query_labs import QUERY_LABS
from .theory import THEORY

FK_NOTE = "Tashqi kalitlarga ON DELETE / ON UPDATE amallarini qo'shmang."
NO_SELECT_NOTE = "Kod oxirida SELECT yozish shart emas: tekshiruv yaratilgan jadvallarni solishtiradi."

DESIGN_LABS = [
    {
        "title": "Loyihalash 1. Asosiy kalit: kitob jadvali",
        "description": f"""\
Kutubxona kitoblarini saqlash uchun «kitob» jadvalini loyihalang.

Talablar:
- Har bir kitob o'zining ISBN raqami bilan aniqlanadi: ikki kitobning ISBN raqami bir xil bo'lmaydi.
- Kitob nomi va muallifi albatta ko'rsatiladi.
- Nashr yili va sahifalar soni noma'lum bo'lishi mumkin.

Ustunlar (nomi va turi aynan shunday bo'lsin):
- isbn — VARCHAR(13)
- nomi — VARCHAR(200)
- muallif — VARCHAR(100)
- yil — INTEGER
- sahifalar — INTEGER

O'zingiz hal qilasiz: qaysi ustun asosiy kalit (PRIMARY KEY) bo'ladi va qaysi ustunlar NOT NULL bo'lishi kerak.

{NO_SELECT_NOTE}""",
        "setup_sql": "",
        "solution_sql": """\
CREATE TABLE kitob (
  isbn VARCHAR(13) PRIMARY KEY,
  nomi VARCHAR(200) NOT NULL,
  muallif VARCHAR(100) NOT NULL,
  yil INTEGER,
  sahifalar INTEGER
);""",
    },
    {
        "title": "Loyihalash 2. Bir-ko'p (1:N) bog'lanish: guruh va talaba",
        "description": f"""\
Universitet guruhlari va talabalari uchun ikki jadval loyihalang: «guruh» va «talaba».

Talablar:
- Har bir guruhning nomi bor: u majburiy va takrorlanmaydi (ikki guruh bir xil nomda bo'lmaydi).
- Har bir talaba albatta bitta guruhga tegishli; bitta guruhda ko'p talaba bo'lishi mumkin.
- Talabaning ismi majburiy.
- Ikkala jadvalda ham id avtomatik oshib boradigan raqam va asosiy kalit.

Ustunlar:
- guruh: id — SERIAL, nomi — VARCHAR(50)
- talaba: id — SERIAL, ism — VARCHAR(100), guruh_id — INTEGER

O'zingiz hal qilasiz: bog'lanish qaysi jadvalda va qanday cheklov bilan ifodalanadi, qaysi ustunlarga NOT NULL va UNIQUE kerak.

{FK_NOTE}
{NO_SELECT_NOTE}""",
        "setup_sql": "",
        "solution_sql": """\
CREATE TABLE guruh (
  id SERIAL PRIMARY KEY,
  nomi VARCHAR(50) NOT NULL UNIQUE
);
CREATE TABLE talaba (
  id SERIAL PRIMARY KEY,
  ism VARCHAR(100) NOT NULL,
  guruh_id INTEGER NOT NULL REFERENCES guruh(id)
);""",
    },
    {
        "title": "Loyihalash 3. Ko'p-ko'p (M:N) bog'lanish: talaba va fan",
        "description": f"""\
Talaba bir nechta fanni tanlashi, bitta fanni esa ko'p talaba o'qishi mumkin — bu «ko'p-ko'p» bog'lanish. \
«talaba» va «fan» jadvallari tayyor (tayyor jadvallarga qarang).

Vazifa:
1. Ular orasidagi bog'lanishni saqlaydigan «talaba_fan» jadvalini yarating:
   - talaba_id — INTEGER, fan_id — INTEGER, baho — INTEGER
   - Bitta talaba bitta fanga faqat bir marta yozilishi mumkin. Asosiy kalitni (talaba_id, fan_id) tartibida yozing.
   - talaba_id va fan_id faqat mavjud talaba va fanga ishora qila olsin.
   - Baho hali qo'yilmagan bo'lishi mumkin.
2. Quyidagi yozuvlarni kiriting (baho hali qo'yilmagan):
   - Ali Valiyev: Ma'lumotlar bazasi, Dasturlash
   - Laylo Rahimova: Ma'lumotlar bazasi, Matematika
   - Bobur Karimov: Dasturlash

{FK_NOTE}
{NO_SELECT_NOTE}""",
        "setup_sql": """\
CREATE TABLE talaba (
  id INTEGER PRIMARY KEY,
  ism VARCHAR(100) NOT NULL
);
CREATE TABLE fan (
  id INTEGER PRIMARY KEY,
  nomi VARCHAR(100) NOT NULL UNIQUE
);
INSERT INTO talaba VALUES (1, 'Ali Valiyev'), (2, 'Laylo Rahimova'), (3, 'Bobur Karimov');
INSERT INTO fan VALUES (1, 'Ma''lumotlar bazasi'), (2, 'Dasturlash'), (3, 'Matematika');""",
        "solution_sql": """\
CREATE TABLE talaba_fan (
  talaba_id INTEGER NOT NULL REFERENCES talaba(id),
  fan_id INTEGER NOT NULL REFERENCES fan(id),
  baho INTEGER,
  PRIMARY KEY (talaba_id, fan_id)
);
INSERT INTO talaba_fan (talaba_id, fan_id) VALUES (1, 1), (1, 2), (2, 1), (2, 3), (3, 2);""",
    },
    {
        "title": "Loyihalash 4. Birinchi normal shakl (1NF): telefon raqamlari",
        "description": f"""\
«talaba_eski» jadvalida bitta katakka bir nechta telefon raqami vergul bilan yozilgan. Bu birinchi normal \
shaklni (1NF) buzadi: har bir katakda faqat bitta, bo'linmas qiymat bo'lishi kerak.

Vazifa:
1. Ikki jadval yarating:
   - «talaba»: id — INTEGER, ism — VARCHAR(100)
   - «talaba_telefon»: talaba_id — INTEGER, telefon — VARCHAR(20)
   Barcha ustunlar majburiy. Har bir jadvalga mos asosiy kalit tanlang: bitta talabaning bir xil raqami ikki marta \
yozilmasin (tarkibli kalit bo'lsa, ustunlarni jadvaldagi tartibda yozing). Telefonni talabaga tashqi kalit bilan bog'lang.
2. Ma'lumotlarni eski jadvaldan yangilariga ko'chiring: har bir telefon raqami alohida qatorda va bo'sh joylarsiz \
bo'lsin. Telefoni yo'q talaba ham «talaba» jadvaliga ko'chirilsin.
3. «talaba_eski» jadvalini o'chirmang.

Maslahat: matnni bo'laklarga ajratish uchun string_to_array(), massivni qatorlarga yoyish uchun unnest(), \
bo'sh joylarni olib tashlash uchun trim() funksiyalari bor.

{FK_NOTE}
{NO_SELECT_NOTE}""",
        "setup_sql": """\
CREATE TABLE talaba_eski (
  id INTEGER PRIMARY KEY,
  ism VARCHAR(100) NOT NULL,
  telefonlar VARCHAR(200)
);
INSERT INTO talaba_eski VALUES
  (1, 'Ali Valiyev', '901234567, 911112233'),
  (2, 'Laylo Rahimova', '935556677'),
  (3, 'Bobur Karimov', '977778899, 900001122, 991234567'),
  (4, 'Madina Yusupova', NULL);""",
        "solution_sql": """\
CREATE TABLE talaba (
  id INTEGER PRIMARY KEY,
  ism VARCHAR(100) NOT NULL
);
CREATE TABLE talaba_telefon (
  talaba_id INTEGER NOT NULL REFERENCES talaba(id),
  telefon VARCHAR(20) NOT NULL,
  PRIMARY KEY (talaba_id, telefon)
);
INSERT INTO talaba (id, ism) SELECT id, ism FROM talaba_eski;
INSERT INTO talaba_telefon (talaba_id, telefon)
SELECT id, trim(raqam)
FROM talaba_eski, unnest(string_to_array(telefonlar, ',')) AS raqam;""",
    },
    {
        "title": "Loyihalash 5. Ikkinchi va uchinchi normal shakl (2NF, 3NF): buyurtmalar",
        "description": f"""\
Do'kon buyurtmalari bitta «buyurtma_eski» jadvalida saqlanadi. Uning asosiy kaliti — (buyurtma_id, mahsulot_kodi). \
Jadvalda ikki muammo bor:
- mahsulot_nomi va narx kalitning faqat bir qismiga (mahsulot_kodi) bog'liq — bu 2NF ni buzadi;
- mijoz_ismi kalitga emas, mijoz_tel ga bog'liq (sana va mijoz_tel esa faqat buyurtma_id ga) — bu 2NF va 3NF ni buzadi.
Natijada bir ma'lumot ko'p marta takrorlanadi va o'zgartirishda xatoliklar paydo bo'ladi.

Vazifa:
1. Jadvalni 3NF dagi to'rtta jadvalga ajrating (barcha ustunlar majburiy):
   - «mijoz»: telefon — VARCHAR(20), ism — VARCHAR(100)
   - «mahsulot»: kod — VARCHAR(10), nomi — VARCHAR(100), narx — NUMERIC(10,2)
   - «buyurtma»: id — INTEGER, sana — DATE, mijoz_tel — VARCHAR(20)
   - «buyurtma_tarkibi»: buyurtma_id — INTEGER, mahsulot_kodi — VARCHAR(10), soni — INTEGER
   Har bir jadvalga asosiy kalit tanlang (tarkibli kalit bo'lsa, ustunlarni jadvaldagi tartibda yozing) va jadvallarni \
tashqi kalitlar bilan bog'lang.
2. Ma'lumotlarni eski jadvaldan yangilariga ko'chiring: har bir mijoz va mahsulot faqat bir marta yozilsin.
3. «buyurtma_eski» jadvalini o'chirmang.

Maslahat: takrorlanuvchi qatorlarni bitta qilib olish uchun SELECT DISTINCT, boshqa jadvaldan ko'chirish uchun \
INSERT INTO ... SELECT ishlating. Jadvallarni to'g'ri tartibda to'ldiring: avval boshqalar ishora qiladigan jadvallar.

{FK_NOTE}
{NO_SELECT_NOTE}""",
        "setup_sql": """\
CREATE TABLE buyurtma_eski (
  buyurtma_id INTEGER NOT NULL,
  sana DATE NOT NULL,
  mijoz_tel VARCHAR(20) NOT NULL,
  mijoz_ismi VARCHAR(100) NOT NULL,
  mahsulot_kodi VARCHAR(10) NOT NULL,
  mahsulot_nomi VARCHAR(100) NOT NULL,
  narx NUMERIC(10,2) NOT NULL,
  soni INTEGER NOT NULL,
  PRIMARY KEY (buyurtma_id, mahsulot_kodi)
);
INSERT INTO buyurtma_eski VALUES
  (1, '2026-09-01', '901112233', 'Ali Valiyev', 'P01', 'Daftar', 5000, 3),
  (1, '2026-09-01', '901112233', 'Ali Valiyev', 'P02', 'Ruchka', 2000, 5),
  (2, '2026-09-02', '935554433', 'Laylo Rahimova', 'P01', 'Daftar', 5000, 1),
  (2, '2026-09-02', '935554433', 'Laylo Rahimova', 'P03', 'Kitob', 45000, 1),
  (3, '2026-09-03', '901112233', 'Ali Valiyev', 'P03', 'Kitob', 45000, 2),
  (4, '2026-09-05', '977001122', 'Bobur Karimov', 'P02', 'Ruchka', 2000, 10);""",
        "solution_sql": """\
CREATE TABLE mijoz (
  telefon VARCHAR(20) PRIMARY KEY,
  ism VARCHAR(100) NOT NULL
);
CREATE TABLE mahsulot (
  kod VARCHAR(10) PRIMARY KEY,
  nomi VARCHAR(100) NOT NULL,
  narx NUMERIC(10,2) NOT NULL
);
CREATE TABLE buyurtma (
  id INTEGER PRIMARY KEY,
  sana DATE NOT NULL,
  mijoz_tel VARCHAR(20) NOT NULL REFERENCES mijoz(telefon)
);
CREATE TABLE buyurtma_tarkibi (
  buyurtma_id INTEGER NOT NULL REFERENCES buyurtma(id),
  mahsulot_kodi VARCHAR(10) NOT NULL REFERENCES mahsulot(kod),
  soni INTEGER NOT NULL,
  PRIMARY KEY (buyurtma_id, mahsulot_kodi)
);
INSERT INTO mijoz (telefon, ism) SELECT DISTINCT mijoz_tel, mijoz_ismi FROM buyurtma_eski;
INSERT INTO mahsulot (kod, nomi, narx) SELECT DISTINCT mahsulot_kodi, mahsulot_nomi, narx FROM buyurtma_eski;
INSERT INTO buyurtma (id, sana, mijoz_tel) SELECT DISTINCT buyurtma_id, sana, mijoz_tel FROM buyurtma_eski;
INSERT INTO buyurtma_tarkibi (buyurtma_id, mahsulot_kodi, soni)
SELECT buyurtma_id, mahsulot_kodi, soni FROM buyurtma_eski;""",
    },
    {
        "title": "Loyihalash 6. Cheklovlar (CHECK, UNIQUE): xodimlar",
        "description": f"""\
Kompaniya bo'limlari va xodimlari uchun ikki jadval loyihalang: «bolim» va «xodim». Biznes qoidalari ma'lumotlar \
bazasining o'zida cheklovlar bilan ta'minlansin, shunda noto'g'ri ma'lumot hech qachon saqlanmaydi.

Ustunlar:
- bolim: id — SERIAL, nomi — VARCHAR(100)
- xodim: id — SERIAL, ism — VARCHAR(100), email — VARCHAR(100), lavozim — VARCHAR(20), maosh — NUMERIC(12,2), \
ishga_kirgan — DATE, bolim_id — INTEGER

Biznes qoidalari:
- Ikkala jadvalda id — asosiy kalit.
- Bo'lim nomi majburiy va takrorlanmaydi.
- Xodimning bolim_id dan boshqa barcha ma'lumotlari majburiy. Yangi xodim hali bo'limga biriktirilmagan bo'lishi \
mumkin, biriktirilgan bo'lsa — faqat mavjud bo'limga.
- Ikki xodimning email manzili bir xil bo'lmaydi.
- Maosh musbat bo'ladi: maosh > 0
- Lavozim faqat uchtadan biri: lavozim IN ('dasturchi', 'tahlilchi', 'rahbar')
- Ishga kirgan sana kelajakda bo'lmaydi: ishga_kirgan <= CURRENT_DATE

CHECK shartlarini aynan yuqoridagi ko'rinishda yozing: tekshiruv ularni matn sifatida solishtiradi.

{FK_NOTE}
{NO_SELECT_NOTE}""",
        "setup_sql": "",
        "solution_sql": """\
CREATE TABLE bolim (
  id SERIAL PRIMARY KEY,
  nomi VARCHAR(100) NOT NULL UNIQUE
);
CREATE TABLE xodim (
  id SERIAL PRIMARY KEY,
  ism VARCHAR(100) NOT NULL,
  email VARCHAR(100) NOT NULL UNIQUE,
  lavozim VARCHAR(20) NOT NULL CHECK (lavozim IN ('dasturchi', 'tahlilchi', 'rahbar')),
  maosh NUMERIC(12,2) NOT NULL CHECK (maosh > 0),
  ishga_kirgan DATE NOT NULL CHECK (ishga_kirgan <= CURRENT_DATE),
  bolim_id INTEGER REFERENCES bolim(id)
);""",
    },
    {
        "title": "Loyihalash 7. Yakuniy loyiha: kutubxona bazasi",
        "description": f"""\
Kutubxona uchun to'liq ma'lumotlar bazasini loyihalang. Unda mualliflar, kitoblar, kitobxonlar va kitob ijarasi \
saqlanadi.

Ustunlar:
- muallif: id — SERIAL, ism — VARCHAR(100)
- kitob: id — SERIAL, nomi — VARCHAR(200), yil — INTEGER
- kitob_muallif: kitob_id — INTEGER, muallif_id — INTEGER
- kitobxon: id — SERIAL, ism — VARCHAR(100), telefon — VARCHAR(20)
- ijara: id — SERIAL, kitob_id — INTEGER, kitobxon_id — INTEGER, olingan — DATE, qaytarilgan — DATE

Talablar:
- muallif, kitob, kitobxon va ijara jadvallarida id — asosiy kalit.
- Bitta kitobning bir nechta muallifi bo'lishi, bitta muallif esa ko'p kitob yozishi mumkin. Bitta muallif bitta \
kitobga ikki marta yozilmasin (tarkibli kalit bo'lsa, ustunlarni jadvaldagi tartibda yozing).
- Muallif ismi va kitob nomi majburiy; nashr yili noma'lum bo'lishi mumkin.
- Kitobxon ismi va telefoni majburiy, ikki kitobxonning telefoni bir xil bo'lmaydi.
- Ijarada kitob, kitobxon va olingan sana majburiy. Qaytarilgan sana kitob qaytarilguncha bo'sh turadi.
- Kitob olingan kunidan oldin qaytarilishi mumkin emas: qaytarilgan >= olingan (CHECK shartini aynan shunday yozing).
- Barcha bog'lanishlar tashqi kalitlar bilan ifodalansin.

{FK_NOTE}
{NO_SELECT_NOTE}""",
        "setup_sql": "",
        "solution_sql": """\
CREATE TABLE muallif (
  id SERIAL PRIMARY KEY,
  ism VARCHAR(100) NOT NULL
);
CREATE TABLE kitob (
  id SERIAL PRIMARY KEY,
  nomi VARCHAR(200) NOT NULL,
  yil INTEGER
);
CREATE TABLE kitob_muallif (
  kitob_id INTEGER NOT NULL REFERENCES kitob(id),
  muallif_id INTEGER NOT NULL REFERENCES muallif(id),
  PRIMARY KEY (kitob_id, muallif_id)
);
CREATE TABLE kitobxon (
  id SERIAL PRIMARY KEY,
  ism VARCHAR(100) NOT NULL,
  telefon VARCHAR(20) NOT NULL UNIQUE
);
CREATE TABLE ijara (
  id SERIAL PRIMARY KEY,
  kitob_id INTEGER NOT NULL REFERENCES kitob(id),
  kitobxon_id INTEGER NOT NULL REFERENCES kitobxon(id),
  olingan DATE NOT NULL,
  qaytarilgan DATE,
  CHECK (qaytarilgan >= olingan)
);""",
    },
]


ER_NOTE = """\
Diagrammani chizish qoidalari:
- Obyekt va atribut nomlarini shartdagidek yozing (katta-kichik harf farqi yo'q).
- Har bir obyektda asosiy kalitni (PK) belgilang.
- Tashqi kalit (FK) atributlarini yozish shart emas: bog'lanishning o'zi ularni ifodalaydi.
- Har bir bog'lanishning ikki uchida kardinallikni tanlang: «1» yoki «N».
- Ko'p-ko'p (M:N) bog'lanishni ikki obyekt orasida to'g'ridan-to'g'ri (N — N) chizing."""


def _entity(entity_id, name, x, y, key, *attributes):
    return {
        "id": entity_id,
        "name": name,
        "x": x,
        "y": y,
        "attributes": [{"name": key, "key": "pk"}] + [{"name": item, "key": ""} for item in attributes],
    }


def _relationship(relationship_id, name, source, source_card, target, target_card):
    return {
        "id": relationship_id,
        "name": name,
        "source": source,
        "target": target,
        "source_card": source_card,
        "target_card": target_card,
    }


ER_LABS = [
    {
        "kind": "er",
        "title": "ER-model 1. Universitet: talaba, guruh va fan",
        "description": f"""\
Universitet uchun konseptual ER-diagramma chizing.

Obyektlar va ularning atributlari:
- Talaba: id, ism, tugilgan_sana
- Guruh: id, nomi
- Fan: id, nomi, kredit

Biznes qoidalari:
- Har bir talaba bitta guruhda o'qiydi, bitta guruhda esa ko'p talaba bo'ladi.
- Talaba bir nechta fanni o'qiydi, bitta fanni esa ko'p talaba o'qiydi.

O'zingiz aniqlaysiz: qaysi obyektlar orasida bog'lanish bor, har bir bog'lanishning kardinalligi va har bir \
obyektning asosiy kaliti.

{ER_NOTE}""",
        "reference_diagram": {
            "entities": [
                _entity("talaba", "Talaba", 40, 160, "id", "ism", "tugilgan_sana"),
                _entity("guruh", "Guruh", 420, 40, "id", "nomi"),
                _entity("fan", "Fan", 420, 300, "id", "nomi", "kredit"),
            ],
            "relationships": [
                _relationship("r1", "a'zo", "talaba", "N", "guruh", "1"),
                _relationship("r2", "o'qiydi", "talaba", "N", "fan", "N"),
            ],
        },
    },
    {
        "kind": "er",
        "title": "ER-model 2. Kutubxona",
        "description": f"""\
Kutubxona uchun konseptual ER-diagramma chizing.

Obyektlar va ularning atributlari:
- Kitob: isbn, nomi, yil
- Muallif: id, ism
- Kitobxon: id, ism, telefon
- Ijara: id, olingan_sana, qaytarilgan_sana

Biznes qoidalari:
- Har bir kitob o'zining ISBN raqami bilan aniqlanadi.
- Bitta kitobni bir nechta muallif birga yozishi, bitta muallif esa ko'p kitob yozishi mumkin.
- Kitobxon kitobni ijaraga oladi. Har bir ijara yozuvi aynan bitta kitob va aynan bitta kitobxonga tegishli; \
bitta kitob va bitta kitobxonning ko'p ijarasi bo'lishi mumkin.

O'zingiz aniqlaysiz: bog'lanishlar, ularning kardinalligi va har bir obyektning asosiy kaliti.

{ER_NOTE}""",
        "reference_diagram": {
            "entities": [
                _entity("kitob", "Kitob", 40, 40, "isbn", "nomi", "yil"),
                _entity("muallif", "Muallif", 440, 40, "id", "ism"),
                _entity("kitobxon", "Kitobxon", 440, 320, "id", "ism", "telefon"),
                _entity("ijara", "Ijara", 40, 320, "id", "olingan_sana", "qaytarilgan_sana"),
            ],
            "relationships": [
                _relationship("r1", "yozgan", "muallif", "N", "kitob", "N"),
                _relationship("r2", "ijaraga beriladi", "kitob", "1", "ijara", "N"),
                _relationship("r3", "ijaraga oladi", "kitobxon", "1", "ijara", "N"),
            ],
        },
    },
    {
        "kind": "er",
        "title": "ER-model 3. Shifoxona: 1:1, 1:N va M:N bog'lanishlar",
        "description": f"""\
Shifoxona uchun konseptual ER-diagramma chizing.

Obyektlar va ularning atributlari:
- Bolim: id, nomi
- Shifokor: id, ism, mutaxassislik
- Bemor: id, ism, tugilgan_sana
- Qabul: id, sana, tashxis
- Dori: id, nomi

Biznes qoidalari:
- Har bir shifokor bitta bo'limda ishlaydi, bo'limda esa ko'p shifokor ishlaydi.
- Har bir bo'limni aynan bitta shifokor boshqaradi va bitta shifokor faqat bitta bo'limni boshqara oladi \
(bu «ishlaydi» bog'lanishidan alohida bog'lanish).
- Qabul — bitta bemorning bitta shifokor qabuliga borishi. Bemor ham, shifokor ham ko'p qabulga ega bo'lishi mumkin.
- Bitta qabulda bir nechta dori yozilishi, bitta dori esa ko'p qabulda yozilishi mumkin.

O'zingiz aniqlaysiz: bog'lanishlar, ularning kardinalligi va har bir obyektning asosiy kaliti.

{ER_NOTE}""",
        "reference_diagram": {
            "entities": [
                _entity("bolim", "Bolim", 40, 40, "id", "nomi"),
                _entity("shifokor", "Shifokor", 420, 40, "id", "ism", "mutaxassislik"),
                _entity("bemor", "Bemor", 800, 300, "id", "ism", "tugilgan_sana"),
                _entity("qabul", "Qabul", 420, 300, "id", "sana", "tashxis"),
                _entity("dori", "Dori", 420, 560, "id", "nomi"),
            ],
            "relationships": [
                _relationship("r1", "ishlaydi", "shifokor", "N", "bolim", "1"),
                _relationship("r2", "boshqaradi", "shifokor", "1", "bolim", "1"),
                _relationship("r3", "qabul qiladi", "shifokor", "1", "qabul", "N"),
                _relationship("r4", "qabulga keladi", "bemor", "1", "qabul", "N"),
                _relationship("r5", "yoziladi", "qabul", "N", "dori", "N"),
            ],
        },
    },
]

# Seed buyrug'i shu tartibda qo'shadi: avval konseptual (ER), keyin fizik (SQL) loyihalash
for _lab in ER_LABS + DESIGN_LABS:
    _lab["theory"] = THEORY.get(_lab["title"], "")

# Kurs tartibida: ER-model → jadvallarni loyihalash → ER-modeldan jadvallarga → SELECT so'rovlari → indekslar
ALL_LABS = ER_LABS + DESIGN_LABS + ER_SQL_LABS + QUERY_LABS + INDEX_LABS
