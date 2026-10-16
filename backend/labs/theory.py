"""Tayyor laboratoriyalar uchun qisqa nazariya va ishlangan namuna (talabaga laboratoriya sahifasida ko'rinadi).

Namunalar ataylab boshqa mavzuda (do'kon, kinoteatr, avtosalon...) yozilgan: ular usulni ko'rsatadi,
lekin laboratoriya yechimini bermaydi. Kod bloklari ``` bilan ajratiladi, qolgani oddiy matn.
"""

THEORY = {
    "Loyihalash 1. Asosiy kalit: kitob jadvali": """\
Asosiy kalit (PRIMARY KEY) jadvaldagi har bir qatorni yagona aniqlaydi. U ikki shartni birga ta'minlaydi: \
qiymat takrorlanmaydi (UNIQUE) va bo'sh bo'lmaydi (NOT NULL). Jadvalda faqat bitta asosiy kalit bo'ladi.

Kalit sifatida tabiatan noyob va o'zgarmaydigan ustun tanlanadi: pasport raqami, avtomobil VIN kodi, mahsulot \
shtrix-kodi. Ism yoki narx kalit bo'la olmaydi — ular takrorlanadi.

NOT NULL — qiymat albatta kiritilishi shart. Ma'lumot noma'lum bo'lishi mumkin bo'lsa, ustun NOT NULL'siz qoladi.

Namuna (boshqa jadval):
```sql
CREATE TABLE avtomobil (
  vin VARCHAR(17) PRIMARY KEY,   -- har bir avtomobilda o'z VIN kodi bor
  rusumi VARCHAR(50) NOT NULL,   -- albatta ma'lum
  rangi VARCHAR(30),             -- noma'lum bo'lishi mumkin
  yurgan_km INTEGER
);
```""",
    "Loyihalash 2. Bir-ko'p (1:N) bog'lanish: guruh va talaba": """\
Bir-ko'p (1:N) bog'lanishda «ko'p» tomondagi jadvalga «bir» tomonga ishora qiluvchi ustun qo'shiladi — tashqi \
kalit (FOREIGN KEY). U faqat mavjud qatorga ishora qila oladi: yo'q yozuvga bog'lab bo'lmaydi.

Tashqi kalit «ko'p» tomonda turadi, chunki bitta qator faqat bitta qiymat saqlaydi. Bog'lanish majburiy bo'lsa \
(har bir yozuv albatta biror joyga tegishli), tashqi kalit ustuniga NOT NULL ham qo'shiladi.

SERIAL — avtomatik oshib boradigan butun son: id ni o'zingiz kiritmaysiz. UNIQUE esa asosiy kalit bo'lmagan \
ustunda takrorlanishni taqiqlaydi.

Namuna (boshqa jadvallar):
```sql
CREATE TABLE kategoriya (
  id SERIAL PRIMARY KEY,
  nomi VARCHAR(50) NOT NULL UNIQUE
);
CREATE TABLE mahsulot (
  id SERIAL PRIMARY KEY,
  nomi VARCHAR(100) NOT NULL,
  -- har bir mahsulot albatta bitta kategoriyaga tegishli
  kategoriya_id INTEGER NOT NULL REFERENCES kategoriya(id)
);
```""",
    "Loyihalash 3. Ko'p-ko'p (M:N) bog'lanish: talaba va fan": """\
Ko'p-ko'p (M:N) bog'lanishni ikki jadvalning o'zida saqlab bo'lmaydi. Uning uchun oraliq (bog'lovchi) jadval \
yaratiladi: unda ikkala jadvalga ishora qiluvchi ikki tashqi kalit bo'ladi.

Bitta juftlik ikki marta yozilmasligi uchun oraliq jadvalning asosiy kaliti tarkibli bo'ladi — ikki ustundan \
iborat: PRIMARY KEY (a_id, b_id). Bog'lanishning o'ziga tegishli ma'lumot (masalan, sana yoki baho) ham shu \
jadvalda saqlanadi.

Bir nechta qatorni bitta INSERT bilan kiritish mumkin: VALUES (...), (...), (...).

Namuna (boshqa jadvallar: film va aktyor):
```sql
CREATE TABLE film_aktyor (
  film_id INTEGER NOT NULL REFERENCES film(id),
  aktyor_id INTEGER NOT NULL REFERENCES aktyor(id),
  rol VARCHAR(100),               -- bog'lanishga tegishli ma'lumot
  PRIMARY KEY (film_id, aktyor_id)
);
INSERT INTO film_aktyor (film_id, aktyor_id) VALUES (1, 2), (1, 3), (2, 2);
```""",
    "Loyihalash 4. Birinchi normal shakl (1NF): telefon raqamlari": """\
Birinchi normal shakl (1NF): har bir katakda bitta, bo'linmas qiymat bo'ladi. Bitta katakka vergul bilan bir \
nechta qiymat yozish 1NF ni buzadi: bunday qiymatni qidirish, tekshirish va o'zgartirish qiyin.

Yechim — takrorlanuvchi qiymatlarni alohida jadvalga chiqarish: har bir qiymat alohida qatorda, asosiy jadvalga \
tashqi kalit bilan bog'langan.

Ma'lumotni ko'chirishda yordam beradigan funksiyalar:
- string_to_array(matn, ',') — matnni bo'laklar massiviga ajratadi;
- unnest(massiv) — massiv elementlarini alohida qatorlarga yoyadi;
- trim(matn) — boshidagi va oxiridagi bo'sh joylarni olib tashlaydi.
INSERT INTO jadval (...) SELECT ... — boshqa jadvaldan olingan qatorlarni kiritadi.

Namuna (funksiyalar qanday ishlashi):
```sql
SELECT trim(rang) AS rang
FROM unnest(string_to_array('qizil, yashil , ko''k', ',')) AS rang;
-- natija: uchta qator — qizil, yashil, ko'k
```
NULL qiymatli katak unnest'da birorta ham qator bermaydi — buni hisobga oling.""",
    "Loyihalash 5. Ikkinchi va uchinchi normal shakl (2NF, 3NF): buyurtmalar": """\
Funksional bog'liqlik A → B: A ma'lum bo'lsa, B aniq bo'ladi (masalan, mahsulot kodi → mahsulot nomi).

2NF: jadval 1NF da va kalit bo'lmagan har bir ustun butun kalitga bog'liq, kalitning bir qismiga emas. Bu faqat \
tarkibli kalitli jadvallarda buziladi.
3NF: jadval 2NF da va kalit bo'lmagan ustun boshqa kalit bo'lmagan ustunga bog'liq emas (tranzitiv bog'liqlik yo'q).

Usul: har bir bog'liqlik uchun alohida jadval yarating — bog'liqlikning chap tomoni shu jadvalning asosiy kaliti \
bo'ladi. Keyin ma'lumotni SELECT DISTINCT bilan ko'chiring, avval boshqalar ishora qiladigan jadvallarni.

Namuna (boshqa jadval): dars(talaba_id, fan_kodi, fan_nomi, baho), kalit — (talaba_id, fan_kodi). \
fan_kodi → fan_nomi bog'liqligi 2NF ni buzadi, shuning uchun fan alohida jadvalga chiqariladi:
```sql
CREATE TABLE fan (
  kod VARCHAR(10) PRIMARY KEY,
  nomi VARCHAR(100) NOT NULL
);
INSERT INTO fan (kod, nomi)
SELECT DISTINCT fan_kodi, fan_nomi FROM dars;   -- har bir fan bir marta
```""",
    "Loyihalash 6. Cheklovlar (CHECK, UNIQUE): xodimlar": """\
Cheklovlar biznes qoidalarini bazaning o'zida ta'minlaydi: dasturda xato bo'lsa ham noto'g'ri ma'lumot saqlanmaydi.

- NOT NULL — qiymat majburiy.
- UNIQUE — takrorlanmaydi (NULL qiymatlar bir nechta bo'lishi mumkin).
- CHECK (shart) — har bir qator shu shartni qanoatlantirishi kerak.
- REFERENCES — faqat mavjud yozuvga ishora. NOT NULL'siz tashqi kalit «hali bog'lanmagan» holatga ruxsat beradi.

CHECK ichida taqqoslash (>, <=), IN (...) ro'yxati va CURRENT_DATE kabi funksiyalarni ishlatish mumkin.

Namuna (boshqa jadval):
```sql
CREATE TABLE chipta (
  id SERIAL PRIMARY KEY,
  joy_raqami VARCHAR(10) NOT NULL UNIQUE,
  turi VARCHAR(10) NOT NULL CHECK (turi IN ('oddiy', 'vip')),
  narx NUMERIC(10,2) NOT NULL CHECK (narx > 0),
  seans_id INTEGER REFERENCES seans(id)   -- hali seansga biriktirilmagan bo'lishi mumkin
);
```""",
    "Loyihalash 7. Yakuniy loyiha: kutubxona bazasi": """\
Yakuniy loyihada oldingi barcha mavzular birlashadi. Tavsiya etilgan tartib:
1. Mustaqil obyektlarni aniqlang (ular boshqa jadvalga ishora qilmaydi) va avval ularni yarating.
2. 1:N bog'lanishlar uchun «ko'p» tomonga tashqi kalit qo'shing.
3. M:N bog'lanishlar uchun tarkibli kalitli oraliq jadval yarating.
4. Har bir ustun uchun so'rang: majburiymi (NOT NULL)? takrorlanmasligi kerakmi (UNIQUE)? qiymatiga shart bormi (CHECK)?

Bir nechta ustunni bog'laydigan CHECK shartini ustun ichida emas, jadval darajasida yozing. Bunday shart \
ustunlardan biri NULL bo'lsa buzilgan hisoblanmaydi.

Namuna (boshqa jadval):
```sql
CREATE TABLE mehmonxona_bron (
  id SERIAL PRIMARY KEY,
  xona_id INTEGER NOT NULL REFERENCES xona(id),
  mehmon_id INTEGER NOT NULL REFERENCES mehmon(id),
  kelish DATE NOT NULL,
  ketish DATE,                    -- hali ma'lum bo'lmasligi mumkin
  CHECK (ketish >= kelish)        -- jadval darajasidagi cheklov
);
```
Yechimni «Sinab ko'rish» bilan bosqichma-bosqich tekshiring: avval jadvallar to'g'ri yaratilishini ko'ring.""",
    "ER-model 1. Universitet: talaba, guruh va fan": """\
ER-model (obyekt–bog'lanish) bazani jadvallardan oldin, tushunchalar darajasida tasvirlaydi:
- Obyekt (entity) — ma'lumot saqlanadigan narsa: mijoz, mahsulot.
- Atribut — obyektning xususiyati: ism, narx. Asosiy kalit (PK) obyektni yagona aniqlaydi.
- Bog'lanish — obyektlar orasidagi aloqa. Kardinallik har bir tomonda nechta bo'lishini ko'rsatadi.

Kardinallikni aniqlash uchun ikkala yo'nalishda so'rang: «bitta A nechta B ga ega?» va «bitta B nechta A ga ega?».
- 1 va N → bir-ko'p (1:N);
- N va N → ko'p-ko'p (M:N).

Namuna (boshqa mavzu: do'kon):
- Mijoz (id, ism) — Buyurtma (id, sana): bitta mijoz ko'p buyurtma beradi, har bir buyurtma bitta mijozniki → 1:N.
- Buyurtma — Mahsulot (id, nomi, narx): buyurtmada ko'p mahsulot, mahsulot ko'p buyurtmada → M:N (N — N).""",
    "ER-model 2. Kutubxona": """\
Obyekt yoki atribut? Agar tushunchaning o'z xususiyatlari bo'lsa yoki u bir nechta obyektga bog'lansa — u alohida \
obyekt. Masalan, «muallif» ning ismi bor va u ko'p kitobga tegishli, shuning uchun u atribut emas, obyekt.

Hodisa (voqea) ham obyekt bo'lishi mumkin: ijara, to'lov, qabul. Bunday obyektning o'z atributlari (sana, summa) \
bo'ladi va u har doim aniq bitta qatnashchilarga bog'lanadi — shuning uchun hodisa ko'p bog'lanishlarning \
«N» tomonida turadi.

Asosiy kalit sifatida tabiiy kalit (ISBN, pasport raqami) yoki sun'iy id ishlatiladi.

Namuna (boshqa mavzu: avtoijaraga berish):
- Avtomobil (vin, rusumi) va Mijoz (id, ism, telefon) — mustaqil obyektlar.
- Ijara (id, boshlanish, tugash) — hodisa: har bir ijara bitta avtomobil va bitta mijozga tegishli.
- Avtomobil 1 — N Ijara, Mijoz 1 — N Ijara.""",
    "ER-model 3. Shifoxona: 1:1, 1:N va M:N bog'lanishlar": """\
Ikki obyekt orasida bir nechta bog'lanish bo'lishi mumkin — har biri o'z ma'nosiga ega. Masalan, xodim bo'limda \
ishlaydi (1:N) va xodim bo'limni boshqaradi (1:1). Ularni ikki alohida bog'lanish sifatida chizing.

Bir-bir (1:1): ikkala tomonda ham «1». Har bir A ga ko'pi bilan bitta B, har bir B ga ko'pi bilan bitta A to'g'ri keladi.

Bog'lanishni to'g'ri aniqlash uchun shartdagi har bir jumlani ikki yo'nalishda tekshiring.

Namuna (boshqa mavzu: maktab):
- O'qituvchi N — 1 Maktab: «ishlaydi» (maktabda ko'p o'qituvchi).
- O'qituvchi 1 — 1 Maktab: «direktor» (har bir maktabda bitta direktor, bitta o'qituvchi bitta maktabga direktor).
- Dars (id, sana) — hodisa: O'qituvchi 1 — N Dars, Sinf 1 — N Dars.
- Dars N — N Mavzu: bitta darsda bir nechta mavzu, bitta mavzu ko'p darsda.""",
}
