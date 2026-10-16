"""SELECT so'rovlari bo'yicha tayyor laboratoriyalar: oddiy filtrdan oyna funksiyalarigacha.

Hammasi bitta «universitet» bazasida (guruh, talaba, fan, baho). Har bir laboratoriyada yashirin test
ma'lumotlari bor: tuzilish bir xil, ma'lumotlar boshqa. Talaba natijani qo'lda yozsa (SELECT 'Ali', 85),
ko'rinadigan ma'lumotlarda o'tadi, lekin yashirinlarida o'tmaydi.

Natija ustunlari nomi solishtirilmaydi, tartibi esa yechimda ORDER BY bo'lsa solishtiriladi. Shuning uchun
shartda saralash to'liq beriladi (teng qiymatlar ham qanday tartiblanishi).

Nazariyadagi namunalar boshqa bazada (do'kon: kategoriya, mahsulot, sotuv) yozilgan.
"""

SCHEMA = """\
CREATE TABLE guruh (
  id INTEGER PRIMARY KEY,
  nomi VARCHAR(20) NOT NULL UNIQUE,
  kurs INTEGER NOT NULL
);
CREATE TABLE talaba (
  id INTEGER PRIMARY KEY,
  ism VARCHAR(50) NOT NULL,
  familiya VARCHAR(50) NOT NULL,
  guruh_id INTEGER REFERENCES guruh(id),
  tugilgan_yil INTEGER NOT NULL,
  shahar VARCHAR(50)
);
CREATE TABLE fan (
  id INTEGER PRIMARY KEY,
  nomi VARCHAR(100) NOT NULL UNIQUE,
  kredit INTEGER NOT NULL
);
CREATE TABLE baho (
  talaba_id INTEGER NOT NULL REFERENCES talaba(id),
  fan_id INTEGER NOT NULL REFERENCES fan(id),
  ball INTEGER NOT NULL CHECK (ball BETWEEN 0 AND 100),
  PRIMARY KEY (talaba_id, fan_id)
);
"""

VISIBLE_DATA = """\
INSERT INTO guruh VALUES (1, 'DI-101', 1), (2, 'DI-102', 1), (3, 'KI-201', 2), (4, 'KI-202', 2);
INSERT INTO talaba VALUES
  (1, 'Ali', 'Valiyev', 1, 2005, 'Toshkent'),
  (2, 'Laylo', 'Rahimova', 1, 2006, 'Samarqand'),
  (3, 'Bobur', 'Karimov', 2, 2005, 'Toshkent'),
  (4, 'Madina', 'Yusupova', 2, 2004, 'Buxoro'),
  (5, 'Jasur', 'Toshmatov', 3, 2003, 'Toshkent'),
  (6, 'Nilufar', 'Qodirova', 3, 2004, NULL),
  (7, 'Sardor', 'Aliyev', 3, 2003, 'Namangan'),
  (8, 'Dilnoza', 'Ergasheva', NULL, 2006, 'Toshkent');
INSERT INTO fan VALUES (1, 'Ma''lumotlar bazasi', 6), (2, 'Dasturlash', 5), (3, 'Matematika', 4), (4, 'Fizika', 3);
INSERT INTO baho VALUES
  (1, 1, 85), (1, 2, 90), (1, 3, 70),
  (2, 1, 92), (2, 3, 88), (2, 4, 80),
  (3, 1, 60), (3, 2, 75),
  (4, 2, 95), (4, 3, 65),
  (5, 1, 78), (5, 2, 82), (5, 3, 91), (5, 4, 72),
  (6, 1, 78),
  (8, 2, 68);
"""

# Yashirin: boshqa ismlar, shaharlar, ballar va qatorlar soni; bo'sh guruhlar, bahosiz talabalar, teng ballar ham bor
HIDDEN_DATA = """\
INSERT INTO guruh VALUES (1, 'MT-101', 1), (2, 'MT-102', 1), (3, 'FI-301', 3), (4, 'FI-302', 3), (5, 'IQ-401', 4);
INSERT INTO talaba VALUES
  (1, 'Otabek', 'Nazarov', 1, 2004, 'Toshkent'),
  (2, 'Gulnora', 'Saidova', 1, 2005, 'Farg''ona'),
  (3, 'Sherzod', 'Umarov', 1, 2006, NULL),
  (4, 'Malika', 'Xolmatova', 2, 2003, 'Toshkent'),
  (5, 'Rustam', 'Haydarov', 2, 2006, 'Andijon'),
  (6, 'Zarina', 'Mirzayeva', 3, 2002, 'Namangan'),
  (7, 'Akmal', 'Sobirov', 3, 2005, 'Toshkent'),
  (8, 'Feruza', 'Azimova', NULL, 2004, 'Buxoro'),
  (9, 'Doniyor', 'Rasulov', 4, 2001, NULL),
  (10, 'Kamola', 'Ismoilova', 4, 2006, 'Toshkent');
INSERT INTO fan VALUES
  (1, 'Algoritmlar', 5), (2, 'Ma''lumotlar bazasi', 6), (3, 'Statistika', 4), (4, 'Ingliz tili', 2), (5, 'Tarix', 2);
INSERT INTO baho VALUES
  (1, 1, 88), (1, 2, 76), (1, 3, 93),
  (2, 1, 64), (2, 2, 81),
  (3, 2, 59), (3, 3, 70), (3, 4, 95),
  (4, 1, 91), (4, 2, 87), (4, 3, 62),
  (5, 1, 73),
  (6, 2, 99), (6, 3, 84),
  (7, 1, 57), (7, 2, 81), (7, 4, 66),
  (8, 3, 77);
"""

SETUP_SQL = SCHEMA + VISIBLE_DATA
HIDDEN_SETUP_SQL = SCHEMA + HIDDEN_DATA

DATA_NOTE = (
    "Tayyor jadvallar: guruh, talaba, fan, baho. Kodingiz boshqa (yashirin) ma'lumotlarda ham tekshiriladi, "
    "shuning uchun natijani qo'lda yozmang — so'rov istalgan ma'lumotlar uchun to'g'ri ishlasin."
)

QUERY_LABS = [
    {
        "title": "So'rov 1. SELECT va WHERE: toshkentlik talabalar",
        "description": f"""\
Toshkentda yashaydigan talabalarning familiyasi va ismini chiqaring.

Natija ustunlari: familiya, ism.
Saralash: familiya bo'yicha alifbo tartibida, familiya bir xil bo'lsa — ism bo'yicha.

{DATA_NOTE}""",
        "solution_sql": "SELECT familiya, ism FROM talaba WHERE shahar = 'Toshkent' ORDER BY familiya, ism;",
        "theory": """\
SELECT so'rovi jadvaldan kerakli ustunlarni oladi, WHERE esa faqat shartga mos qatorlarni qoldiradi. \
ORDER BY natijani saralaydi: ASC — o'sish (odatiy), DESC — kamayish. Bir nechta ustun berilsa, avval birinchisi \
bo'yicha, teng bo'lsa keyingisi bo'yicha saralanadi.

Matn qiymatlari bitta tirnoqda yoziladi: 'Toshkent'. Qo'shtirnoq ("...") ustun nomi uchun ishlatiladi.

Namuna (boshqa baza: do'kon):
```sql
SELECT nomi, narx
FROM mahsulot
WHERE narx < 50000
ORDER BY narx DESC, nomi;
```""",
    },
    {
        "title": "So'rov 2. Saralash va LIMIT: eng yosh talabalar",
        "description": f"""\
Eng yosh 3 talabaning ismi, familiyasi va tug'ilgan yilini chiqaring.

Natija ustunlari: ism, familiya, tugilgan_yil.
Saralash: tug'ilgan yil bo'yicha kamayish tartibida (eng yoshi birinchi); yili bir xil bo'lsa — id bo'yicha o'sish \
tartibida. Natijada aynan 3 ta qator bo'lsin.

{DATA_NOTE}""",
        "solution_sql": "SELECT ism, familiya, tugilgan_yil FROM talaba ORDER BY tugilgan_yil DESC, id LIMIT 3;",
        "theory": """\
LIMIT n natijadan faqat dastlabki n qatorni qoldiradi. U deyarli har doim ORDER BY bilan birga ishlatiladi: \
saralanmagan natijaning «dastlabki» qatorlari tasodifiy bo'ladi.

Teng qiymatlar bo'lsa, qaysi qator kirishi saralashning ikkinchi ustuniga bog'liq. Shuning uchun natija aniq \
bo'lishi uchun noyob ustun (masalan, id) ham qo'shiladi. OFFSET m esa dastlabki m qatorni tashlab o'tadi.

Namuna (boshqa baza: do'kon):
```sql
-- eng qimmat 5 ta mahsulot; narxi teng bo'lsa, id kichigi oldin
SELECT nomi, narx
FROM mahsulot
ORDER BY narx DESC, id
LIMIT 5;
```""",
    },
    {
        "title": "So'rov 3. NULL va IN: shahri noma'lum yoki viloyatdan",
        "description": f"""\
Shahri ko'rsatilmagan (NULL) yoki Buxoro yoki Namanganda yashaydigan talabalarning ismi va familiyasini chiqaring.

Natija ustunlari: ism, familiya.
Saralash: id bo'yicha o'sish tartibida.

{DATA_NOTE}""",
        "solution_sql": """\
SELECT ism, familiya FROM talaba
WHERE shahar IS NULL OR shahar IN ('Buxoro', 'Namangan')
ORDER BY id;""",
        "theory": """\
NULL — «qiymat noma'lum» degani. U hech narsaga teng emas, hatto o'ziga ham: shahar = NULL sharti hech qachon \
rost bo'lmaydi. NULL ni tekshirish uchun IS NULL yoki IS NOT NULL ishlatiladi.

IN (a, b, c) — qiymat ro'yxatdagilardan biriga tengmi: x = a OR x = b OR x = c ning qisqa yozilishi.

Shartlarni AND va OR bilan birlashtirganda AND kuchliroq: a OR b AND c — bu a OR (b AND c). Shubha bo'lsa, \
qavs qo'ying.

Namuna (boshqa baza: do'kon):
```sql
SELECT nomi
FROM mahsulot
WHERE kategoriya_id IS NULL OR kategoriya_id IN (2, 3)
ORDER BY id;
```""",
    },
    {
        "title": "So'rov 4. Agregat funksiyalar: baholar statistikasi",
        "description": f"""\
Barcha qo'yilgan baholar bo'yicha bitta qatorli statistika chiqaring.

Natija ustunlari (aynan shu tartibda):
- baholar soni;
- o'rtacha ball, 2 xonagacha yaxlitlangan: ROUND(..., 2);
- eng yuqori ball;
- eng past ball.

{DATA_NOTE}""",
        "solution_sql": "SELECT COUNT(*), ROUND(AVG(ball), 2), MAX(ball), MIN(ball) FROM baho;",
        "theory": """\
Agregat funksiyalar ko'p qatordan bitta qiymat hisoblaydi:
- COUNT(*) — qatorlar soni; COUNT(ustun) — shu ustunda NULL bo'lmagan qiymatlar soni;
- SUM, AVG — yig'indi va o'rtacha; MIN, MAX — eng kichik va eng katta.

GROUP BY bo'lmasa, butun jadval bitta guruh hisoblanadi va natija bitta qator bo'ladi. AVG ko'p xonali kasr \
qaytaradi, ROUND(qiymat, 2) uni 2 xonagacha yaxlitlaydi.

Namuna (boshqa baza: do'kon):
```sql
SELECT COUNT(*) AS mahsulotlar,
       ROUND(AVG(narx), 2) AS ortacha_narx,
       SUM(ombor_soni) AS jami_omborda
FROM mahsulot;
```""",
    },
    {
        "title": "So'rov 5. INNER JOIN: talabalar va guruhlar",
        "description": f"""\
Har bir talabaning familiyasi, ismi va guruhi nomini chiqaring. Guruhga biriktirilmagan talabalar natijaga kirmasin.

Natija ustunlari: familiya, ism, guruh nomi.
Saralash: guruh nomi bo'yicha, bitta guruh ichida — familiya bo'yicha.

{DATA_NOTE}""",
        "solution_sql": """\
SELECT t.familiya, t.ism, g.nomi
FROM talaba t
JOIN guruh g ON g.id = t.guruh_id
ORDER BY g.nomi, t.familiya;""",
        "theory": """\
JOIN ikki jadval qatorlarini shart bo'yicha juftlaydi. INNER JOIN (yoki shunchaki JOIN) faqat juftligi topilgan \
qatorlarni qoldiradi: tashqi kaliti NULL bo'lgan qator natijaga kirmaydi.

Jadvallarga qisqa nom (taxallus) berish qulay: FROM mahsulot m. Ikkala jadvalda bir xil nomli ustun bo'lsa \
(masalan, id yoki nomi), qaysi jadvalniki ekanini ko'rsating: m.nomi, k.nomi.

Namuna (boshqa baza: do'kon):
```sql
SELECT m.nomi, k.nomi AS kategoriya
FROM mahsulot m
JOIN kategoriya k ON k.id = m.kategoriya_id
ORDER BY k.nomi, m.nomi;
```""",
    },
    {
        "title": "So'rov 6. LEFT JOIN: birorta ham bahosi yo'q talabalar",
        "description": f"""\
Hali birorta ham baho olmagan talabalarning familiyasi va ismini chiqaring.

Natija ustunlari: familiya, ism.
Saralash: familiya bo'yicha.

{DATA_NOTE}""",
        "solution_sql": """\
SELECT t.familiya, t.ism
FROM talaba t
LEFT JOIN baho b ON b.talaba_id = t.id
WHERE b.talaba_id IS NULL
ORDER BY t.familiya;""",
        "theory": """\
LEFT JOIN chap jadvalning barcha qatorlarini saqlaydi. O'ng jadvalda juftligi topilmasa, o'ng jadval \
ustunlari NULL bo'ladi. Shu xususiyat «juftligi yo'q» qatorlarni topishga imkon beradi: LEFT JOIN, keyin \
WHERE o'ng_jadval.ustun IS NULL.

Xuddi shu natijani NOT EXISTS (SELECT 1 FROM ... WHERE ...) bilan ham olish mumkin.

Namuna (boshqa baza: do'kon):
```sql
-- birorta ham marta sotilmagan mahsulotlar
SELECT m.nomi
FROM mahsulot m
LEFT JOIN sotuv s ON s.mahsulot_id = m.id
WHERE s.id IS NULL
ORDER BY m.nomi;
```""",
    },
    {
        "title": "So'rov 7. GROUP BY va HAVING: fanlar bo'yicha o'rtacha ball",
        "description": f"""\
Har bir fan bo'yicha baholar sonini va o'rtacha ballni chiqaring. Faqat kamida 3 ta bahosi bor fanlar \
natijaga kirsin.

Natija ustunlari: fan nomi, baholar soni, o'rtacha ball (ROUND(..., 2)).
Saralash: o'rtacha ball bo'yicha kamayish tartibida.

{DATA_NOTE}""",
        "solution_sql": """\
SELECT f.nomi, COUNT(*), ROUND(AVG(b.ball), 2)
FROM baho b
JOIN fan f ON f.id = b.fan_id
GROUP BY f.id, f.nomi
HAVING COUNT(*) >= 3
ORDER BY 3 DESC;""",
        "theory": """\
GROUP BY qatorlarni ustun qiymati bo'yicha guruhlaydi va agregat funksiyani har bir guruh uchun alohida \
hisoblaydi. SELECT da faqat GROUP BY dagi ustunlar va agregatlar bo'lishi mumkin.

Asosiy kalit bo'yicha guruhlansa (GROUP BY m.id), PostgreSQL shu jadvalning boshqa ustunlarini ham SELECT da \
yozishga ruxsat beradi: ular kalitga bog'liq.

WHERE guruhlashdan oldin qatorlarni filtrlaydi, HAVING esa guruhlashdan keyin guruhlarni: agregatga shart \
(COUNT(*) >= 3) faqat HAVING da yoziladi.

Bajarilish tartibi: FROM → WHERE → GROUP BY → HAVING → SELECT → ORDER BY.

Namuna (boshqa baza: do'kon):
```sql
-- jami kamida 10 dona sotilgan mahsulotlar
SELECT m.nomi, SUM(s.soni) AS jami
FROM sotuv s
JOIN mahsulot m ON m.id = s.mahsulot_id
GROUP BY m.id, m.nomi
HAVING SUM(s.soni) >= 10
ORDER BY jami DESC;
```""",
    },
    {
        "title": "So'rov 8. Ichma-ich so'rov: o'rtachadan yaxshi o'qiydiganlar",
        "description": f"""\
O'rtacha bali barcha baholarning umumiy o'rtachasidan yuqori bo'lgan talabalarni chiqaring.

Natija ustunlari: familiya, ism, talabaning o'rtacha bali (ROUND(..., 2)).
Saralash: o'rtacha ball bo'yicha kamayish tartibida.
Umumiy o'rtacha qo'lda yozilmasin: u ma'lumotlarga qarab o'zgaradi, so'rovning o'zida hisoblang.

{DATA_NOTE}""",
        "solution_sql": """\
SELECT t.familiya, t.ism, ROUND(AVG(b.ball), 2) AS ortacha
FROM talaba t
JOIN baho b ON b.talaba_id = t.id
GROUP BY t.id, t.familiya, t.ism
HAVING AVG(b.ball) > (SELECT AVG(ball) FROM baho)
ORDER BY ortacha DESC;""",
        "theory": """\
Ichma-ich so'rov (subquery) — qavs ichidagi boshqa so'rov. Agar u bitta qiymat qaytarsa, uni oddiy son kabi \
taqqoslashda ishlatish mumkin: narx > (SELECT AVG(narx) FROM mahsulot).

Bunday so'rov ma'lumot o'zgarganda ham to'g'ri ishlaydi. Hisoblangan sonni qo'lda yozish esa faqat bugungi \
ma'lumotlar uchun to'g'ri bo'ladi.

Ichma-ich so'rov ro'yxat ham qaytarishi mumkin: WHERE id IN (SELECT ...).

Namuna (boshqa baza: do'kon):
```sql
-- narxi o'rtacha narxdan yuqori mahsulotlar
SELECT nomi, narx
FROM mahsulot
WHERE narx > (SELECT AVG(narx) FROM mahsulot)
ORDER BY narx DESC;
```""",
    },
    {
        "title": "So'rov 9. Oyna funksiyalari: har bir fan bo'yicha reyting",
        "description": f"""\
Har bir fan ichida talabalarni ball bo'yicha reytinglang: eng yuqori ball — 1-o'rin. Teng ball olgan talabalar \
bir xil o'rinni egallaydi, keyingi o'rin esa tashlab o'tiladi (masalan: 1, 2, 2, 4).

Natija ustunlari: fan nomi, familiya, ball, o'rin.
Saralash: fan nomi bo'yicha, fan ichida — o'rin bo'yicha, o'rin bir xil bo'lsa — familiya bo'yicha.

{DATA_NOTE}""",
        "solution_sql": """\
SELECT f.nomi, t.familiya, b.ball,
       RANK() OVER (PARTITION BY b.fan_id ORDER BY b.ball DESC) AS orin
FROM baho b
JOIN fan f ON f.id = b.fan_id
JOIN talaba t ON t.id = b.talaba_id
ORDER BY f.nomi, orin, t.familiya;""",
        "theory": """\
Oyna funksiyasi har bir qator uchun qiymat hisoblaydi, lekin GROUP BY dan farqli ravishda qatorlarni birlashtirmaydi. \
OVER (...) qaysi qatorlar «oyna» ekanini aytadi: PARTITION BY — oynalarga bo'lish, ORDER BY — oyna ichida tartib.

O'rin raqamlash funksiyalari:
- ROW_NUMBER() — 1, 2, 3, 4 (tenglar ham turli raqam oladi);
- RANK() — 1, 2, 2, 4 (tenglar bir xil o'rin, keyingisi tashlab o'tiladi);
- DENSE_RANK() — 1, 2, 2, 3 (tashlab o'tilmaydi).

Namuna (boshqa baza: do'kon):
```sql
-- har bir kategoriya ichida mahsulotlar narx bo'yicha
SELECT k.nomi AS kategoriya, m.nomi, m.narx,
       DENSE_RANK() OVER (PARTITION BY m.kategoriya_id ORDER BY m.narx DESC) AS orin
FROM mahsulot m
JOIN kategoriya k ON k.id = m.kategoriya_id
ORDER BY kategoriya, orin, m.nomi;
```""",
    },
    {
        "title": "So'rov 10. Yakuniy: har bir guruhning eng yaxshi talabasi",
        "description": f"""\
Har bir guruhdan o'rtacha bali eng yuqori bo'lgan bitta talabani chiqaring. Faqat bahosi bor talabalar \
hisobga olinadi; birorta talabasi baho olmagan guruh natijaga kirmaydi. O'rtacha bali teng bo'lsa, id si \
kichik talaba tanlanadi.

Natija ustunlari: guruh nomi, familiya, ism, o'rtacha ball (ROUND(..., 2)).
Saralash: guruh nomi bo'yicha.

{DATA_NOTE}""",
        "solution_sql": """\
WITH ortacha AS (
  SELECT t.id, t.guruh_id, t.familiya, t.ism, AVG(b.ball) AS ball
  FROM talaba t
  JOIN baho b ON b.talaba_id = t.id
  WHERE t.guruh_id IS NOT NULL
  GROUP BY t.id
),
reyting AS (
  SELECT ortacha.*, ROW_NUMBER() OVER (PARTITION BY guruh_id ORDER BY ball DESC, id) AS n
  FROM ortacha
)
SELECT g.nomi, r.familiya, r.ism, ROUND(r.ball, 2)
FROM reyting r
JOIN guruh g ON g.id = r.guruh_id
WHERE r.n = 1
ORDER BY g.nomi;""",
        "theory": """\
Murakkab so'rovni bosqichlarga bo'lish uchun WITH (umumiy jadval ifodasi, CTE) ishlatiladi: har bir bosqichga nom \
beriladi va keyingi bosqich undan oddiy jadval kabi foydalanadi.

«Har bir guruhning eng yaxshisi» kabi masalalar uchun odatiy usul:
1. Har bir obyekt uchun kerakli qiymatni hisoblang (GROUP BY).
2. Guruh ichida ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...) bilan raqamlang.
3. Faqat 1-raqamlilarni qoldiring.

Namuna (boshqa baza: do'kon):
```sql
-- har bir kategoriyaning eng ko'p sotilgan mahsuloti
WITH jami AS (
  SELECT m.id, m.kategoriya_id, m.nomi, SUM(s.soni) AS soni
  FROM mahsulot m
  JOIN sotuv s ON s.mahsulot_id = m.id
  GROUP BY m.id
),
reyting AS (
  SELECT jami.*, ROW_NUMBER() OVER (PARTITION BY kategoriya_id ORDER BY soni DESC, id) AS n
  FROM jami
)
SELECT k.nomi AS kategoriya, r.nomi, r.soni
FROM reyting r
JOIN kategoriya k ON k.id = r.kategoriya_id
WHERE r.n = 1
ORDER BY kategoriya;
```""",
    },
]

for _lab in QUERY_LABS:
    _lab["setup_sql"] = SETUP_SQL
    _lab["hidden_setup_sql"] = HIDDEN_SETUP_SQL

# Nazariyadagi namunalarni tekshirish uchun (testlarda): do'kon bazasi
EXAMPLE_SETUP_SQL = """\
CREATE TABLE kategoriya (id INTEGER PRIMARY KEY, nomi VARCHAR(50) NOT NULL);
CREATE TABLE mahsulot (
  id INTEGER PRIMARY KEY, nomi VARCHAR(100) NOT NULL, kategoriya_id INTEGER REFERENCES kategoriya(id),
  narx NUMERIC(10,2) NOT NULL, ombor_soni INTEGER NOT NULL
);
CREATE TABLE sotuv (id INTEGER PRIMARY KEY, mahsulot_id INTEGER NOT NULL REFERENCES mahsulot(id), soni INTEGER NOT NULL);
INSERT INTO kategoriya VALUES (1, 'Kanselyariya'), (2, 'Kitob'), (3, 'Elektronika');
INSERT INTO mahsulot VALUES
  (1, 'Daftar', 1, 5000, 100), (2, 'Ruchka', 1, 2000, 300), (3, 'Roman', 2, 45000, 20),
  (4, 'Lug''at', 2, 60000, 5), (5, 'Quloqchin', 3, 150000, 12), (6, 'Fleshka', NULL, 80000, 30);
INSERT INTO sotuv VALUES (1, 1, 7), (2, 1, 5), (3, 2, 9), (4, 3, 2), (5, 5, 1);
"""
