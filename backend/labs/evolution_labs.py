"""Sxemani rivojlantirish (migratsiya) bo'yicha tayyor laboratoriyalar (labs/evolution.py).

Har birida: eski sxema va ma'lumotlar (setup_sql), buyurtmachining yangi talabi, namunaviy migratsiya va ilovaning
yangi so'rovlari. Yashirin ma'lumotlar (hidden_setup_sql) qiymatlarni qo'lda yozib qo'yishni ushlaydi.
"""

EVOLUTION_NOTE = (
    "Jadvallarni o'chirib qayta yaratmang va qiymatlarni qo'lda yozmang: migratsiya mavjud ma'lumotlarni saqlashi va "
    "istalgan ma'lumotlar uchun ishlashi kerak (tekshiruv boshqa, yashirin ma'lumotlarda ham takrorlanadi). Oxirida "
    "SELECT yozish shart emas: tekshiruv jadvallarni va «Ilovaning yangi so'rovlari»ni o'zi bajaradi."
)

THEORY_EVOLUTION = """\
Ishlab turgan bazada jadvalni o'chirib qayta yaratib bo'lmaydi — unda foydalanuvchilarning ma'lumotlari bor. Talab
o'zgarganda sxema migratsiya bilan bosqichma-bosqich o'zgartiriladi:

1. Yangi tuzilmani qo'shish (ma'lumot hali yo'q bo'lgani uchun NOT NULLsiz):
   ALTER TABLE xodim ADD COLUMN shahar VARCHAR(50), ADD COLUMN kocha VARCHAR(100);

2. Ma'lumotni ko'chirish — bitta UPDATE yoki INSERT ... SELECT bilan, hamma qatorlar uchun:
   UPDATE xodim SET shahar = split_part(manzil, ',', 1), kocha = trim(split_part(manzil, ',', 2));
   INSERT INTO lavozim (nomi) SELECT DISTINCT lavozim FROM xodim;

3. Cheklovlarni qo'shish (endi ma'lumot to'ldirilgan):
   ALTER TABLE xodim ALTER COLUMN shahar SET NOT NULL;
   ALTER TABLE xodim ADD FOREIGN KEY (lavozim_id) REFERENCES lavozim (id);

4. Eskisini olib tashlash:
   ALTER TABLE xodim DROP COLUMN manzil;

Foydali funksiyalar: split_part(matn, ajratuvchi, n), trim, lower, string_to_array va unnest (bir katakdagi ro'yxatni
qatorlarga yoyish), DISTINCT, INSERT ... SELECT, UPDATE ... FROM (boshqa jadval bilan bog'lab yangilash)."""

EVOLUTION_LABS = [
    {
        "title": "Migratsiya 1. Do'kon: to'liq ismni ism va familiyaga ajratish",
        "description": f"""\
Onlayn do'kon bazasida mijozning to'liq ismi bitta «fio» ustunida saqlanadi. Yangi talab: marketing bo'limi \
mijozlarni familiya bo'yicha qidirmoqchi va xatlarda faqat ismini yozmoqchi.

Migratsiya yozing:
1. «mijoz» jadvaliga «ism» va «familiya» ustunlarini qo'shing (VARCHAR(50), ikkalasi ham majburiy — NOT NULL).
2. Ularni «fio» dan to'ldiring: birinchi so'z — ism, ikkinchisi — familiya (barcha ismlar ikki so'zdan iborat).
3. Eski «fio» ustunini olib tashlang.

{EVOLUTION_NOTE}""",
        "setup_sql": """\
CREATE TABLE mijoz (
  id INTEGER PRIMARY KEY,
  fio VARCHAR(100) NOT NULL,
  telefon VARCHAR(20)
);
INSERT INTO mijoz VALUES
  (1, 'Ali Valiyev', '+998901112233'),
  (2, 'Laylo Karimova', NULL),
  (3, 'Bobur Valiyev', '+998935556677');""",
        "hidden_setup_sql": """\
CREATE TABLE mijoz (
  id INTEGER PRIMARY KEY,
  fio VARCHAR(100) NOT NULL,
  telefon VARCHAR(20)
);
INSERT INTO mijoz VALUES
  (4, 'Sardor Toshev', NULL),
  (7, 'Madina Valiyeva', '+998977778899'),
  (8, 'Jasur Valiyev', NULL),
  (12, 'Nilufar Aliyeva', '+998901234567');""",
        "solution_sql": """\
ALTER TABLE mijoz ADD COLUMN ism VARCHAR(50), ADD COLUMN familiya VARCHAR(50);
UPDATE mijoz SET ism = split_part(fio, ' ', 1), familiya = split_part(fio, ' ', 2);
ALTER TABLE mijoz ALTER COLUMN ism SET NOT NULL, ALTER COLUMN familiya SET NOT NULL;
ALTER TABLE mijoz DROP COLUMN fio;""",
        "check_queries": [
            {"id": "qidiruv", "title": "Familiya bo'yicha qidiruv",
             "sql": "SELECT id, ism FROM mijoz WHERE familiya = 'Valiyev' ORDER BY id"},
            {"id": "royxat", "title": "Mijozlar ro'yxati (familiya, ism)",
             "sql": "SELECT familiya, ism, telefon FROM mijoz ORDER BY familiya, ism"},
        ],
        "theory": THEORY_EVOLUTION,
        "level": 2,
    },
    {
        "title": "Migratsiya 2. Kutubxona: muallifni alohida jadvalga chiqarish",
        "description": f"""\
Kutubxona bazasida muallif ismi har bir kitobda matn sifatida takrorlanadi («kitob.muallif»). Yangi talab: \
mualliflar haqida qo'shimcha ma'lumot (tug'ilgan yili) saqlanadi va muallif nomi bir joyda o'zgartiriladi.

Migratsiya yozing:
1. «muallif» jadvalini yarating: id (SERIAL PRIMARY KEY), ism (VARCHAR(100) NOT NULL UNIQUE), tugilgan_yil (INTEGER).
2. Mavjud kitoblardagi har bir muallifni bir martadan «muallif» jadvaliga qo'shing — ism bo'yicha alifbo tartibida \
(shunda id'lar 1 dan boshlab shu tartibda beriladi).
3. «kitob» jadvaliga «muallif_id» ustunini qo'shing (NOT NULL, «muallif» ga FOREIGN KEY) va uni to'ldiring.
4. Eski «kitob.muallif» ustunini olib tashlang.

{EVOLUTION_NOTE}""",
        "setup_sql": """\
CREATE TABLE kitob (
  id INTEGER PRIMARY KEY,
  nomi VARCHAR(200) NOT NULL,
  muallif VARCHAR(100) NOT NULL,
  yil INTEGER
);
INSERT INTO kitob VALUES
  (1, 'O''tkan kunlar', 'Abdulla Qodiriy', 1926),
  (2, 'Mehrobdan chayon', 'Abdulla Qodiriy', 1929),
  (3, 'Kecha va kunduz', 'Cho''lpon', 1936),
  (4, 'Sarob', 'Abdulla Qahhor', 1937);""",
        "hidden_setup_sql": """\
CREATE TABLE kitob (
  id INTEGER PRIMARY KEY,
  nomi VARCHAR(200) NOT NULL,
  muallif VARCHAR(100) NOT NULL,
  yil INTEGER
);
INSERT INTO kitob VALUES
  (10, 'Xamsa', 'Alisher Navoiy', 1483),
  (11, 'Boburnoma', 'Zahiriddin Muhammad Bobur', 1530),
  (12, 'Mahbub ul-qulub', 'Alisher Navoiy', 1500);""",
        "solution_sql": """\
CREATE TABLE muallif (
  id SERIAL PRIMARY KEY,
  ism VARCHAR(100) NOT NULL UNIQUE,
  tugilgan_yil INTEGER
);
INSERT INTO muallif (ism) SELECT DISTINCT muallif FROM kitob ORDER BY muallif;
ALTER TABLE kitob ADD COLUMN muallif_id INTEGER REFERENCES muallif (id);
UPDATE kitob SET muallif_id = muallif.id FROM muallif WHERE muallif.ism = kitob.muallif;
ALTER TABLE kitob ALTER COLUMN muallif_id SET NOT NULL;
ALTER TABLE kitob DROP COLUMN muallif;""",
        "check_queries": [
            {"id": "katalog", "title": "Katalog: kitob va muallifi",
             "sql": "SELECT k.nomi, m.ism FROM kitob k JOIN muallif m ON m.id = k.muallif_id ORDER BY k.id"},
            {"id": "mualliflar", "title": "Mualliflar va kitoblari soni",
             "sql": "SELECT m.ism, count(k.id) FROM muallif m LEFT JOIN kitob k ON k.muallif_id = m.id "
                    "GROUP BY m.ism ORDER BY m.ism"},
        ],
        "theory": THEORY_EVOLUTION,
        "level": 3,
    },
    {
        "title": "Migratsiya 3. Klinika: bir katakdagi telefonlarni alohida jadvalga",
        "description": f"""\
Klinika bazasida bemorning telefonlari bitta ustunda vergul bilan yozilgan: «+998901112233,+998935556677». \
Yangi talab: SMS xizmati har bir raqamga alohida murojaat qiladi va bir raqam ikki bemorda bo'lsa, buni ko'rish kerak \
(1NF buzilishini tuzatish).

Migratsiya yozing:
1. «bemor_telefon» jadvalini yarating: bemor_id (INTEGER NOT NULL, «bemor» ga FOREIGN KEY), telefon (VARCHAR(20) NOT \
NULL), asosiy kalit (bemor_id, telefon).
2. «bemor.telefonlar» dagi har bir raqamni alohida qator qilib ko'chiring (bo'sh joylarsiz; telefoni yo'q bemor uchun \
qator bo'lmaydi).
3. Eski «telefonlar» ustunini olib tashlang.

{EVOLUTION_NOTE}""",
        "setup_sql": """\
CREATE TABLE bemor (
  id INTEGER PRIMARY KEY,
  fio VARCHAR(100) NOT NULL,
  telefonlar VARCHAR(200)
);
INSERT INTO bemor VALUES
  (1, 'Aziz Karimov', '+998901112233,+998935556677'),
  (2, 'Malika Yusupova', '+998977778899'),
  (3, 'Sardor Aliyev', NULL),
  (4, 'Dilnoza Karimova', '+998901112233, +998999990000');""",
        "hidden_setup_sql": """\
CREATE TABLE bemor (
  id INTEGER PRIMARY KEY,
  fio VARCHAR(100) NOT NULL,
  telefonlar VARCHAR(200)
);
INSERT INTO bemor VALUES
  (5, 'Jasur Toshev', '+998900000001, +998900000002, +998900000003'),
  (6, 'Nodira Saidova', NULL),
  (9, 'Otabek Rasulov', '+998900000002');""",
        "solution_sql": """\
CREATE TABLE bemor_telefon (
  bemor_id INTEGER NOT NULL REFERENCES bemor (id),
  telefon VARCHAR(20) NOT NULL,
  PRIMARY KEY (bemor_id, telefon)
);
INSERT INTO bemor_telefon (bemor_id, telefon)
SELECT id, trim(raqam) FROM bemor, unnest(string_to_array(telefonlar, ',')) AS raqam
WHERE telefonlar IS NOT NULL;
ALTER TABLE bemor DROP COLUMN telefonlar;""",
        "check_queries": [
            {"id": "sms", "title": "SMS uchun raqamlar ro'yxati",
             "sql": "SELECT b.fio, t.telefon FROM bemor b JOIN bemor_telefon t ON t.bemor_id = b.id ORDER BY b.id, t.telefon"},
            {"id": "umumiy", "title": "Bir nechta bemorda uchragan raqamlar",
             "sql": "SELECT telefon, count(*) FROM bemor_telefon GROUP BY telefon HAVING count(*) > 1 ORDER BY telefon"},
        ],
        "theory": THEORY_EVOLUTION,
        "level": 4,
    },
]
