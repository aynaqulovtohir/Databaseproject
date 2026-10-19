"""Ma'lumotlar ombori (yulduz sxema, analitik so'rovlar) va yarim tuzilmali ma'lumot (JSONB) bo'yicha tayyor laboratoriyalar.

Yulduz sxema va JSON → jadval laboratoriyalari migratsiya kabi tekshiriladi (labs/evolution.py: jadvallar va tekshiruv
so'rovlari), analitik va JSONB so'rovlari — oddiy SQL laboratoriyasi kabi (natija namunaviy yechim bilan solishtiriladi).
Hammasida yashirin ma'lumotlar bor: natijani qo'lda yozib bo'lmaydi.
"""

NO_HARDCODE_NOTE = (
    "Qiymatlarni qo'lda yozmang: tekshiruv boshqa (yashirin) ma'lumotlarda ham takrorlanadi."
)

THEORY_STAR = """\
Ma'lumotlar ombori (OLAP) kundalik ish bazasidan (OLTP) farq qiladi: u yangilash uchun emas, katta hajmdagi tahlil uchun.
Eng ko'p ishlatiladigan tuzilma — yulduz sxema:
- fakt jadvali — o'lchanadigan hodisalar (sotuv, qo'ng'iroq): sonlar (miqdor, summa) va o'lchovlarga havolalar;
- o'lchov (dimension) jadvallari — «kim, nima, qayerda, qachon»: har bir qiymat bir marta, tavsif atributlari bilan.

Misol (boshqa mavzu — kutubxona berishlari):
CREATE TABLE dim_kitob (nomi VARCHAR(100) PRIMARY KEY, janr VARCHAR(50) NOT NULL);
INSERT INTO dim_kitob SELECT DISTINCT kitob, janr FROM berish;
CREATE TABLE fakt_berish (
  sana DATE NOT NULL REFERENCES dim_sana (sana),
  kitob VARCHAR(100) NOT NULL REFERENCES dim_kitob (nomi),
  kunlar INTEGER NOT NULL
);
INSERT INTO fakt_berish SELECT sana, kitob, qaytgan - olingan FROM berish;

Sana o'lchovi: EXTRACT(YEAR FROM sana), EXTRACT(MONTH FROM sana), EXTRACT(QUARTER FROM sana) (natijasini ::int ga
keltiring). Haqiqiy omborlarda o'lchovlar sun'iy kalit (surrogate key) bilan bog'lanadi; bu laboratoriyada sodda
bo'lishi uchun tabiiy kalit (nom, sana) ishlatiladi."""

THEORY_ROLLUP = """\
Hisobotlarda ko'pincha oraliq jamilar kerak: har bir shahar bo'yicha, har bir shaharning har bir oyi bo'yicha va umumiy
jami. Bir nechta so'rovni UNION qilish o'rniga GROUP BY ROLLUP:

SELECT viloyat, tuman, sum(aholi)
FROM aholi_soni
GROUP BY ROLLUP (viloyat, tuman)
ORDER BY viloyat NULLS LAST, tuman NULLS LAST;

ROLLUP (a, b) guruhlari: (a, b), (a) — b bo'yicha oraliq jami, () — umumiy jami. Jami qatorlarda guruhlanmagan
ustun NULL bo'ladi. Uni matn bilan almashtirish: COALESCE(tuman, 'Jami') — yoki GROUPING(tuman) = 1 bo'lsa jami qator.
CUBE (a, b) esa barcha kombinatsiyalarni beradi: (a, b), (a), (b), ()."""

THEORY_JSONB = """\
JSONB — PostgreSQL'da JSON hujjatni ikkilik ko'rinishda saqlaydigan tur. U har xil tuzilmali ma'lumot uchun qulay
(masalan, telefonda «xotira», kiyimda «o'lcham»), lekin qoidalarni (NOT NULL, FOREIGN KEY) baza tekshira olmaydi.

Operatorlar (boshqa misolda):
- xususiyat -> 'kalit'    — qiymat JSON sifatida;
- xususiyat ->> 'kalit'   — qiymat matn sifatida (taqqoslash uchun): WHERE malumot ->> 'shahar' = 'Toshkent';
- (xususiyat ->> 'yosh')::int — sonli solishtirish uchun turini o'zgartirish;
- xususiyat @> '{"faol": true}' — hujjat shu juftlikni o'z ichiga oladimi (GIN indeks bilan tez);
- xususiyat ? 'telefon'   — shunday kalit bormi.

Massiv elementlarini qatorlarga yoyish:
SELECT a.id, e ->> 'nomi', (e ->> 'soni')::int
FROM ariza a, jsonb_array_elements(a.malumot -> 'hujjatlar') AS e;

Qachon JSONB, qachon jadval: tuzilmasi oldindan noma'lum, kam so'raladigan atributlar — JSONB; doimiy, bog'lanadigan,
tez-tez qidiriladigan ma'lumot — oddiy ustun va jadvallar."""

SALES_COLUMNS = """\
CREATE TABLE savdo (
  id INTEGER PRIMARY KEY,
  sana DATE NOT NULL,
  dokon VARCHAR(50) NOT NULL,
  shahar VARCHAR(50) NOT NULL,
  mahsulot VARCHAR(50) NOT NULL,
  kategoriya VARCHAR(50) NOT NULL,
  miqdor INTEGER NOT NULL,
  narx NUMERIC(10, 2) NOT NULL
);"""

SALES_SETUP = SALES_COLUMNS + """
INSERT INTO savdo VALUES
  (1, '2026-01-15', 'Chilonzor', 'Toshkent', 'Daftar', 'Kanselyariya', 10, 5000),
  (2, '2026-01-20', 'Chilonzor', 'Toshkent', 'Kitob', 'Kitoblar', 2, 45000),
  (3, '2026-02-03', 'Registon', 'Samarqand', 'Daftar', 'Kanselyariya', 5, 5000),
  (4, '2026-04-11', 'Registon', 'Samarqand', 'Ruchka', 'Kanselyariya', 20, 2000),
  (5, '2026-04-11', 'Yunusobod', 'Toshkent', 'Kitob', 'Kitoblar', 1, 45000),
  (6, '2026-05-30', 'Chilonzor', 'Toshkent', 'Ruchka', 'Kanselyariya', 15, 2000);"""

SALES_HIDDEN = SALES_COLUMNS + """
INSERT INTO savdo VALUES
  (11, '2025-12-31', 'Markaz', 'Buxoro', 'Atlas', 'Kitoblar', 3, 30000),
  (12, '2026-03-01', 'Markaz', 'Buxoro', 'Qalam', 'Kanselyariya', 40, 1500),
  (13, '2026-03-01', 'Sergeli', 'Toshkent', 'Atlas', 'Kitoblar', 1, 30000),
  (14, '2026-07-07', 'Sergeli', 'Toshkent', 'Qalam', 'Kanselyariya', 12, 1500);"""

STAR_SOLUTION = """\
CREATE TABLE dim_sana (
  sana DATE PRIMARY KEY,
  yil INTEGER NOT NULL,
  oy INTEGER NOT NULL,
  chorak INTEGER NOT NULL
);
INSERT INTO dim_sana
SELECT DISTINCT sana, EXTRACT(YEAR FROM sana)::int, EXTRACT(MONTH FROM sana)::int, EXTRACT(QUARTER FROM sana)::int
FROM savdo;

CREATE TABLE dim_dokon (nomi VARCHAR(50) PRIMARY KEY, shahar VARCHAR(50) NOT NULL);
INSERT INTO dim_dokon SELECT DISTINCT dokon, shahar FROM savdo;

CREATE TABLE dim_mahsulot (nomi VARCHAR(50) PRIMARY KEY, kategoriya VARCHAR(50) NOT NULL);
INSERT INTO dim_mahsulot SELECT DISTINCT mahsulot, kategoriya FROM savdo;

CREATE TABLE fakt_savdo (
  sana DATE NOT NULL REFERENCES dim_sana (sana),
  dokon VARCHAR(50) NOT NULL REFERENCES dim_dokon (nomi),
  mahsulot VARCHAR(50) NOT NULL REFERENCES dim_mahsulot (nomi),
  miqdor INTEGER NOT NULL,
  summa NUMERIC(12, 2) NOT NULL
);
INSERT INTO fakt_savdo SELECT sana, dokon, mahsulot, miqdor, miqdor * narx FROM savdo;"""

STAR_TABLES = """\
CREATE TABLE dim_sana (sana DATE PRIMARY KEY, yil INTEGER NOT NULL, oy INTEGER NOT NULL, chorak INTEGER NOT NULL);
CREATE TABLE dim_dokon (nomi VARCHAR(50) PRIMARY KEY, shahar VARCHAR(50) NOT NULL);
CREATE TABLE dim_mahsulot (nomi VARCHAR(50) PRIMARY KEY, kategoriya VARCHAR(50) NOT NULL);
CREATE TABLE fakt_savdo (
  sana DATE NOT NULL REFERENCES dim_sana (sana),
  dokon VARCHAR(50) NOT NULL REFERENCES dim_dokon (nomi),
  mahsulot VARCHAR(50) NOT NULL REFERENCES dim_mahsulot (nomi),
  miqdor INTEGER NOT NULL,
  summa NUMERIC(12, 2) NOT NULL
);"""

STAR_DATA = """
INSERT INTO dim_sana VALUES
  ('2026-01-15', 2026, 1, 1), ('2026-02-03', 2026, 2, 1), ('2026-04-11', 2026, 4, 2), ('2026-05-30', 2026, 5, 2),
  ('2026-08-19', 2026, 8, 3);
INSERT INTO dim_dokon VALUES ('Chilonzor', 'Toshkent'), ('Yunusobod', 'Toshkent'), ('Registon', 'Samarqand');
INSERT INTO dim_mahsulot VALUES ('Daftar', 'Kanselyariya'), ('Ruchka', 'Kanselyariya'), ('Kitob', 'Kitoblar');
INSERT INTO fakt_savdo VALUES
  ('2026-01-15', 'Chilonzor', 'Daftar', 10, 50000), ('2026-01-15', 'Yunusobod', 'Kitob', 2, 90000),
  ('2026-02-03', 'Registon', 'Daftar', 5, 25000), ('2026-04-11', 'Registon', 'Ruchka', 20, 40000),
  ('2026-05-30', 'Chilonzor', 'Ruchka', 15, 30000), ('2026-08-19', 'Registon', 'Kitob', 1, 45000);"""

STAR_HIDDEN_DATA = """
INSERT INTO dim_sana VALUES ('2025-11-02', 2025, 11, 4), ('2026-03-01', 2026, 3, 1), ('2026-03-09', 2026, 3, 1);
INSERT INTO dim_dokon VALUES ('Markaz', 'Buxoro'), ('Sergeli', 'Toshkent');
INSERT INTO dim_mahsulot VALUES ('Atlas', 'Kitoblar'), ('Qalam', 'Kanselyariya');
INSERT INTO fakt_savdo VALUES
  ('2025-11-02', 'Markaz', 'Atlas', 3, 90000), ('2026-03-01', 'Markaz', 'Qalam', 40, 60000),
  ('2026-03-09', 'Sergeli', 'Atlas', 1, 30000), ('2026-03-09', 'Sergeli', 'Qalam', 2, 3000);"""

PRODUCTS_COLUMNS = """\
CREATE TABLE mahsulot (
  id INTEGER PRIMARY KEY,
  nomi VARCHAR(100) NOT NULL,
  narx NUMERIC(12, 2) NOT NULL,
  xususiyat JSONB NOT NULL
);"""

PRODUCTS_SETUP = PRODUCTS_COLUMNS + """
INSERT INTO mahsulot VALUES
  (1, 'Telefon A', 3500000, '{"turi": "telefon", "rang": "qora", "xotira": 128, "5g": true}'),
  (2, 'Telefon B', 2100000, '{"turi": "telefon", "rang": "oq", "xotira": 64}'),
  (3, 'Telefon C', 5200000, '{"turi": "telefon", "rang": "qora", "xotira": 256, "5g": true}'),
  (4, 'Futbolka', 120000, '{"turi": "kiyim", "rang": "qora", "olcham": "L"}'),
  (5, 'Telefon D', 2900000, '{"turi": "telefon", "rang": "qora", "xotira": 128}');"""

PRODUCTS_HIDDEN = PRODUCTS_COLUMNS + """
INSERT INTO mahsulot VALUES
  (10, 'Telefon X', 4100000, '{"turi": "telefon", "rang": "kok", "xotira": 512, "5g": true}'),
  (11, 'Telefon Y', 1500000, '{"turi": "telefon", "rang": "qora", "xotira": 32, "5g": true}'),
  (12, 'Telefon Z', 6000000, '{"turi": "telefon", "rang": "qora", "xotira": 1024, "5g": true}'),
  (13, 'Kurtka', 900000, '{"turi": "kiyim", "rang": "qora", "5g": true}'),
  (14, 'Telefon W', 3000000, '{"turi": "telefon", "rang": "qora", "xotira": 128, "5g": false}');"""

ORDERS_JSON_COLUMNS = """\
CREATE TABLE buyurtma (
  id INTEGER PRIMARY KEY,
  malumot JSONB NOT NULL
);"""

ORDERS_JSON_SETUP = ORDERS_JSON_COLUMNS + """
INSERT INTO buyurtma VALUES
  (1, '{"mijoz": "Ali", "mahsulotlar": [{"nomi": "Daftar", "soni": 3}, {"nomi": "Ruchka", "soni": 2}]}'),
  (2, '{"mijoz": "Laylo", "mahsulotlar": [{"nomi": "Kitob", "soni": 1}]}'),
  (3, '{"mijoz": "Vali", "mahsulotlar": []}');"""

ORDERS_JSON_HIDDEN = ORDERS_JSON_COLUMNS + """
INSERT INTO buyurtma VALUES
  (7, '{"mijoz": "Sardor", "mahsulotlar": [{"nomi": "Atlas", "soni": 1}, {"nomi": "Qalam", "soni": 10},
                                            {"nomi": "Globus", "soni": 2}]}'),
  (9, '{"mijoz": "Nodira", "mahsulotlar": [{"nomi": "Qalam", "soni": 4}]}');"""

WAREHOUSE_LABS = [
    {
        "title": "Ombor 1. Savdo jadvalidan yulduz sxema",
        "description": f"""\
Do'konlar tarmog'ining barcha sotuvlari bitta «savdo» jadvalida: do'kon va shahar, mahsulot va kategoriya har bir \
qatorda takrorlanadi. Tahlil bo'limi uchun shu ma'lumotdan yulduz sxema quring (eski «savdo» jadvalini qoldiring):

1. dim_sana (sana DATE PRIMARY KEY, yil, oy, chorak — INTEGER NOT NULL) — savdoda uchragan har bir sana.
2. dim_dokon (nomi VARCHAR(50) PRIMARY KEY, shahar VARCHAR(50) NOT NULL).
3. dim_mahsulot (nomi VARCHAR(50) PRIMARY KEY, kategoriya VARCHAR(50) NOT NULL).
4. fakt_savdo: sana, dokon, mahsulot (NOT NULL, mos o'lchovga FOREIGN KEY), miqdor INTEGER NOT NULL, \
summa NUMERIC(12, 2) NOT NULL = miqdor × narx. Har bir sotuv — bitta qator.

{NO_HARDCODE_NOTE}""",
        "setup_sql": SALES_SETUP,
        "hidden_setup_sql": SALES_HIDDEN,
        "solution_sql": STAR_SOLUTION,
        "check_queries": [
            {"id": "shahar-oy", "title": "Shahar va oy bo'yicha tushum",
             "sql": "SELECT d.shahar, s.yil, s.oy, sum(f.summa) FROM fakt_savdo f "
                    "JOIN dim_dokon d ON d.nomi = f.dokon JOIN dim_sana s ON s.sana = f.sana "
                    "GROUP BY d.shahar, s.yil, s.oy ORDER BY d.shahar, s.yil, s.oy"},
            {"id": "kategoriya", "title": "Kategoriya va chorak bo'yicha sotilgan dona",
             "sql": "SELECT m.kategoriya, s.chorak, sum(f.miqdor) FROM fakt_savdo f "
                    "JOIN dim_mahsulot m ON m.nomi = f.mahsulot JOIN dim_sana s ON s.sana = f.sana "
                    "GROUP BY m.kategoriya, s.chorak ORDER BY m.kategoriya, s.chorak"},
            {"id": "toliq", "title": "Fakt jadvalida har bir sotuv bor",
             "sql": "SELECT count(*), sum(summa) FROM fakt_savdo"},
        ],
        "theory": THEORY_STAR,
        "topic": "warehouse",
        "level": 3,
    },
    {
        "title": "Ombor 2. Analitik hisobot: ROLLUP bilan oraliq jamilar",
        "description": f"""\
Yulduz sxema tayyor (fakt_savdo, dim_dokon, dim_sana, dim_mahsulot). Rahbar uchun bitta so'rov bilan hisobot chiqaring: \
har bir shahar va har bir do'kon tushumi, har bir shahar bo'yicha oraliq jami va umumiy jami.

Ustunlar: shahar, dokon, tushum (summa yig'indisi). Shahar jami qatorida dokon = 'Jami', umumiy jami qatorida \
shahar = 'Hammasi' va dokon = 'Jami'. Tartib: shahar bo'yicha (umumiy jami oxirida), shahar ichida do'kon bo'yicha \
(shahar jami do'konlardan keyin).

{NO_HARDCODE_NOTE}""",
        "setup_sql": STAR_TABLES + STAR_DATA,
        "hidden_setup_sql": STAR_TABLES + STAR_HIDDEN_DATA,
        "solution_sql": """\
SELECT COALESCE(d.shahar, 'Hammasi') AS shahar,
       COALESCE(d.nomi, 'Jami') AS dokon,
       sum(f.summa) AS tushum
FROM fakt_savdo f JOIN dim_dokon d ON d.nomi = f.dokon
GROUP BY ROLLUP (d.shahar, d.nomi)
ORDER BY GROUPING(d.shahar), d.shahar, GROUPING(d.nomi), d.nomi;""",
        "theory": THEORY_ROLLUP,
        "topic": "warehouse",
        "level": 3,
    },
    {
        "title": "JSONB 1. Har xil xususiyatli mahsulotlarni qidirish",
        "description": f"""\
Internet-do'konda mahsulotlarning xususiyatlari har xil, shuning uchun ular JSONB ustunida saqlanadi \
(«xususiyat»). Xaridor filtri: qora rangli, 5G qo'llab-quvvatlaydigan («5g»: true) va xotirasi kamida 128 GB \
bo'lgan telefonlar.

Ustunlar: nomi, narx, xotira (son sifatida). Tartib: narx bo'yicha o'sish.

{NO_HARDCODE_NOTE}""",
        "setup_sql": PRODUCTS_SETUP,
        "hidden_setup_sql": PRODUCTS_HIDDEN,
        "solution_sql": """\
SELECT nomi, narx, (xususiyat ->> 'xotira')::int AS xotira
FROM mahsulot
WHERE xususiyat @> '{"turi": "telefon", "rang": "qora", "5g": true}'
  AND (xususiyat ->> 'xotira')::int >= 128
ORDER BY narx;""",
        "theory": THEORY_JSONB,
        "topic": "json",
        "level": 2,
    },
    {
        "title": "JSONB 2. JSON hujjatlardan relyatsion jadvalga",
        "description": f"""\
Buyurtmalar tashqi tizimdan JSON ko'rinishida kelib, «buyurtma.malumot» ustunida saqlangan: \
{{"mijoz": "...", "mahsulotlar": [{{"nomi": "...", "soni": ...}}]}}. Hisobotlar uchun ularni jadvallarga o'tkazing:

1. «buyurtma» jadvaliga «mijoz» ustunini qo'shing (VARCHAR(100) NOT NULL) va JSON'dan to'ldiring.
2. «buyurtma_qator» jadvalini yarating: buyurtma_id (INTEGER NOT NULL, «buyurtma» ga FOREIGN KEY), mahsulot \
(VARCHAR(100) NOT NULL), soni (INTEGER NOT NULL); asosiy kalit (buyurtma_id, mahsulot). Har bir mahsulot — bitta qator.
3. «malumot» ustunini olib tashlang.

{NO_HARDCODE_NOTE}""",
        "setup_sql": ORDERS_JSON_SETUP,
        "hidden_setup_sql": ORDERS_JSON_HIDDEN,
        "solution_sql": """\
ALTER TABLE buyurtma ADD COLUMN mijoz VARCHAR(100);
UPDATE buyurtma SET mijoz = malumot ->> 'mijoz';
ALTER TABLE buyurtma ALTER COLUMN mijoz SET NOT NULL;

CREATE TABLE buyurtma_qator (
  buyurtma_id INTEGER NOT NULL REFERENCES buyurtma (id),
  mahsulot VARCHAR(100) NOT NULL,
  soni INTEGER NOT NULL,
  PRIMARY KEY (buyurtma_id, mahsulot)
);
INSERT INTO buyurtma_qator
SELECT b.id, e ->> 'nomi', (e ->> 'soni')::int
FROM buyurtma b, jsonb_array_elements(b.malumot -> 'mahsulotlar') AS e;

ALTER TABLE buyurtma DROP COLUMN malumot;""",
        "check_queries": [
            {"id": "hisobot", "title": "Mijoz va mahsulotlar",
             "sql": "SELECT b.mijoz, q.mahsulot, q.soni FROM buyurtma b JOIN buyurtma_qator q ON q.buyurtma_id = b.id "
                    "ORDER BY b.id, q.mahsulot"},
            {"id": "jami", "title": "Mahsulot bo'yicha jami dona",
             "sql": "SELECT mahsulot, sum(soni) FROM buyurtma_qator GROUP BY mahsulot ORDER BY mahsulot"},
            {"id": "bosh", "title": "Mahsulotsiz buyurtmalar ham saqlangan",
             "sql": "SELECT b.mijoz FROM buyurtma b LEFT JOIN buyurtma_qator q ON q.buyurtma_id = b.id "
                    "WHERE q.buyurtma_id IS NULL ORDER BY b.id"},
        ],
        "theory": THEORY_JSONB,
        "topic": "json",
        "level": 3,
    },
]
