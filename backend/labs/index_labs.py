"""Indeks va EXPLAIN bo'yicha tayyor laboratoriyalar.

Talaba indeks yaratadi; tekshiruv shartdagi so'rovning rejasini (EXPLAIN) oladi va unda taqiqlangan
tugunlar (Seq Scan, Sort) yo'qligini ko'radi. Jadval ma'lumotlari o'zgarmasligi ham tekshiriladi
(namunaviy yechim bilan solishtiriladi), shuning uchun jadvalni bo'shatib yoki almashtirib aldab bo'lmaydi.

Kichik jadvalda PostgreSQL indeksni baribir ishlatmaydi: shuning uchun ma'lumotlar generate_series bilan
o'n minglab qator qilib yaratiladi va ANALYZE bilan statistika yig'iladi.
"""

NO_SELECT_NOTE = "Kod oxirida SELECT yozish shart emas: tekshiruv so'rov rejasini va jadvallarni tekshiradi."
EXPLAIN_NOTE = (
    "Rejani «Sinab ko'rish» bilan ko'ring: natija ostida «So'rov rejasi (EXPLAIN)» ko'rsatiladi. Jadval "
    "ma'lumotlarini o'zgartirmang, faqat indeks yarating."
)

USERS_SETUP = """\
CREATE TABLE foydalanuvchi (
  id INTEGER PRIMARY KEY,
  email VARCHAR(100) NOT NULL,
  ism VARCHAR(50) NOT NULL,
  shahar VARCHAR(50) NOT NULL,
  royxatdan_otgan DATE NOT NULL
);
INSERT INTO foydalanuvchi
SELECT g,
       'user' || g || '@pochta.uz',
       (ARRAY['Ali', 'Laylo', 'Bobur', 'Madina', 'Jasur', 'Nilufar'])[g % 6 + 1],
       (ARRAY['Toshkent', 'Samarqand', 'Buxoro', 'Namangan', 'Andijon'])[g % 5 + 1],
       DATE '2020-01-01' + g % 2000
FROM generate_series(1, 50000) AS g;
ANALYZE foydalanuvchi;"""

ORDERS_SETUP = """\
CREATE TABLE buyurtma (
  id INTEGER PRIMARY KEY,
  mijoz_id INTEGER NOT NULL,
  sana DATE NOT NULL,
  summa NUMERIC(10,2) NOT NULL,
  holat VARCHAR(20) NOT NULL
);
INSERT INTO buyurtma
SELECT g,
       g % 2000 + 1,
       DATE '2024-01-01' + (g * 7) % 900,
       (g * 37) % 500000 / 100.0 + 10,
       (ARRAY['yangi', 'tolangan', 'yetkazilgan', 'bekor'])[g % 4 + 1]
FROM generate_series(1, 60000) AS g;
ANALYZE buyurtma;"""

CUSTOMERS_SETUP = """\
CREATE TABLE mijoz (
  id INTEGER PRIMARY KEY,
  email VARCHAR(100) NOT NULL,
  ism VARCHAR(50) NOT NULL
);
INSERT INTO mijoz
SELECT g,
       (ARRAY['Ali.Valiyev', 'LAYLO.R', 'bobur.karimov', 'Madina.Yusupova'])[g % 4 + 1] || g || '@Pochta.UZ',
       (ARRAY['Ali', 'Laylo', 'Bobur', 'Madina'])[g % 4 + 1]
FROM generate_series(1, 50000) AS g;
ANALYZE mijoz;"""

INDEX_LABS = [
    {
        "title": "Indeks 1. B-tree indeks: email bo'yicha qidirish",
        "description": f"""\
«foydalanuvchi» jadvalida 50 000 ta yozuv bor. Tizimga kirishda foydalanuvchi email bo'yicha qidiriladi:

SELECT id, ism FROM foydalanuvchi WHERE email = 'user31415@pochta.uz';

Hozir bu so'rov butun jadvalni boshidan oxirigacha o'qiydi (rejada «Seq Scan»). Shu so'rovni tezlashtiradigan \
indeks yarating: rejada Seq Scan qolmasin.

{EXPLAIN_NOTE}
{NO_SELECT_NOTE}""",
        "setup_sql": USERS_SETUP,
        "solution_sql": "CREATE INDEX foydalanuvchi_email_idx ON foydalanuvchi (email);",
        "plan_query": "SELECT id, ism FROM foydalanuvchi WHERE email = 'user31415@pochta.uz'",
        "plan_forbidden": "Seq Scan",
        "theory": """\
Indekssiz PostgreSQL shartga mos qatorni topish uchun jadvalning har bir qatorini tekshiradi — Seq Scan \
(ketma-ket o'qish). Katta jadvalda bu sekin.

Indeks — ustun qiymatlari tartiblangan alohida tuzilma (odatda B-tree). U kitob oxiridagi mundarijaga \
o'xshaydi: kerakli qiymatga darhol boriladi — Index Scan.

EXPLAIN so'rovni bajarmasdan uning rejasini ko'rsatadi. Rejani pastdan yuqoriga o'qing: eng ichki tugun \
ma'lumot qanday o'qilishini aytadi.

Indeks bepul emas: u joy egallaydi va har bir INSERT/UPDATE da yangilanadi. Shuning uchun faqat ko'p \
qidiriladigan ustunlarga yaratiladi.

Namuna (boshqa jadval):
```sql
CREATE TABLE avtomobil (id INTEGER PRIMARY KEY, raqam VARCHAR(10) NOT NULL);
CREATE INDEX avtomobil_raqam_idx ON avtomobil (raqam);
EXPLAIN SELECT id FROM avtomobil WHERE raqam = '01A777AA';
```""",
    },
    {
        "title": "Indeks 2. Tarkibli indeks: qidirish va saralash",
        "description": f"""\
«buyurtma» jadvalida 60 000 ta buyurtma bor (2 000 ta mijoz). Mijoz sahifasida uning oxirgi 10 ta buyurtmasi \
ko'rsatiladi:

SELECT sana, summa FROM buyurtma WHERE mijoz_id = 777 ORDER BY sana DESC LIMIT 10;

Shu so'rov uchun indeks yarating: rejada jadvalni to'liq o'qish (Seq Scan) ham, natijani alohida saralash \
(Sort) ham bo'lmasin.

Maslahat: faqat mijoz_id ga indeks qo'yib, rejada nima qolishini ko'ring.

{EXPLAIN_NOTE}
{NO_SELECT_NOTE}""",
        "setup_sql": ORDERS_SETUP,
        "solution_sql": "CREATE INDEX buyurtma_mijoz_sana_idx ON buyurtma (mijoz_id, sana);",
        "plan_query": "SELECT sana, summa FROM buyurtma WHERE mijoz_id = 777 ORDER BY sana DESC LIMIT 10",
        "plan_forbidden": "Seq Scan, Sort",
        "theory": """\
Tarkibli indeks bir nechta ustunni birga tartiblaydi: (a, b) indeksida qatorlar avval a, keyin a ichida b \
bo'yicha joylashadi. Telefon kitobiga o'xshaydi: familiya, keyin ism.

Shuning uchun (a, b) indeksi quyidagilarga yordam beradi:
- WHERE a = ... (faqat birinchi ustun bo'yicha ham);
- WHERE a = ... AND b = ...;
- WHERE a = ... ORDER BY b — natija indeksdan tayyor tartibda olinadi, Sort kerak emas
  (B-tree ikkala yo'nalishda o'qiladi, shuning uchun ORDER BY b DESC ham).
Lekin faqat WHERE b = ... ga deyarli yordam bermaydi: ustunlar tartibi muhim.

Namuna (boshqa jadval):
```sql
CREATE TABLE xabar (id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, yuborilgan TIMESTAMP NOT NULL);
-- chat ichidagi oxirgi xabarlar: avval chat, keyin vaqt
CREATE INDEX xabar_chat_vaqt_idx ON xabar (chat_id, yuborilgan);
EXPLAIN SELECT id FROM xabar WHERE chat_id = 5 ORDER BY yuborilgan DESC LIMIT 20;
```""",
    },
    {
        "title": "Indeks 3. Ifoda bo'yicha indeks: katta-kichik harfsiz qidirish",
        "description": f"""\
«mijoz» jadvalida email manzillar turli harflarda saqlangan (Ali.Valiyev12@Pochta.UZ). Qidiruv katta-kichik \
harfni farqlamasligi uchun so'rov lower() funksiyasidan foydalanadi:

SELECT id, ism FROM mijoz WHERE lower(email) = 'ali.valiyev12@pochta.uz';

Shu so'rov uchun indeks yarating: rejada Seq Scan qolmasin. Ma'lumotlarni o'zgartirmang (masalan, emailni \
kichik harfga o'tkazmang).

Maslahat: oddiy email indeksi bilan rejada nima o'zgarishini avval sinab ko'ring.

{EXPLAIN_NOTE}
{NO_SELECT_NOTE}""",
        "setup_sql": CUSTOMERS_SETUP,
        "solution_sql": "CREATE INDEX mijoz_email_lower_idx ON mijoz (lower(email));",
        "plan_query": "SELECT id, ism FROM mijoz WHERE lower(email) = 'ali.valiyev12@pochta.uz'",
        "plan_forbidden": "Seq Scan",
        "theory": """\
Oddiy indeks ustunning o'z qiymatlarini saqlaydi. Shartda ustun funksiya ichida bo'lsa (lower(email), \
date(vaqt), narx * 1.12), indeksdagi qiymatlar bilan solishtirib bo'lmaydi va PostgreSQL yana Seq Scan qiladi.

Ifoda bo'yicha indeks ifodaning natijasini saqlaydi. U ishlatilishi uchun so'rovdagi ifoda indeksdagi \
ifodaga aynan mos bo'lishi kerak. Ifoda qavs ichida yoziladi: CREATE INDEX ... ON jadval ((ifoda)); \
oddiy funksiya chaqiruvi uchun bitta qavs ham yetadi.

Namuna (boshqa jadval):
```sql
CREATE TABLE kitob (id INTEGER PRIMARY KEY, nomi VARCHAR(200) NOT NULL);
-- nomini harflar farqisiz qidirish
CREATE INDEX kitob_nomi_upper_idx ON kitob (upper(nomi));
EXPLAIN SELECT id FROM kitob WHERE upper(nomi) = 'ALPOMISH';
```""",
    },
]
