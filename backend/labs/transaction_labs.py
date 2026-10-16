"""Tranzaksiyalar bo'yicha tayyor laboratoriyalar: parallel tranzaksiyalardagi anomaliyalar.

Talaba kodi (BEGIN ... COMMIT) ikki sessiyada bir vaqtda, eng xavfli tartibda bajariladi: A ning COMMIT gacha
bo'lgan buyruqlari, keyin B ning, keyin A COMMIT va B COMMIT (sandbox.run_concurrent). Kod to'g'ri bo'lishi
uchun parallel natija ketma-ket ikki marta bajarilgandagi natijaga teng bo'lishi kerak.

Namunalar boshqa mavzularda (layk hisoblagich, kinoteatr o'rindig'i) yozilgan.
"""

CONCURRENCY_NOTE = """\
Tekshiruv: kodingiz ikki sessiyada (A va B) bir vaqtda bajariladi — A COMMIT qilishidan oldin B ham ishlay \
boshlaydi. Natija kod ketma-ket ikki marta bajarilgandagidek bo'lishi kerak. «Sinab ko'rish» vaqt chizig'ini \
ko'rsatadi: qaysi sessiya nimani o'qidi va qayerda qulf kutdi.
Kod bitta tranzaksiya bo'lsin: BEGIN bilan boshlanib, COMMIT bilan tugasin."""

TRANSACTION_LABS = [
    {
        "title": "Tranzaksiya 1. Yo'qolgan yangilanish: hisobdan pul yechish",
        "description": f"""\
Mijoz 1-hisobidan 100 000 so'm yechmoqda. Bitta tranzaksiyada:
1. 1-hisob balansini 100 000 ga kamaytiring.
2. «amaliyot» jadvaliga yozuv qo'shing: hisob_id = 1, summa = 100000.

Xuddi shu paytda ikkinchi bankomatda ham xuddi shunday yechish bajarilishi mumkin. Ikkala yechish ham to'g'ri \
hisobga olinishi kerak: 500 000 dan ikki marta 100 000 yechilsa, 300 000 qolsin.

Ko'p uchraydigan xato: avval balansni o'qib (SELECT), keyin «o'qilgan qiymat − 100 000» ni yozish. Bitta \
sessiyada bu to'g'ri ishlaydi — ikki sessiyada nima bo'lishini «Sinab ko'rish» bilan ko'ring.

{CONCURRENCY_NOTE}""",
        "setup_sql": """\
CREATE TABLE hisob (
  id INTEGER PRIMARY KEY,
  egasi VARCHAR(100) NOT NULL,
  balans NUMERIC(12,2) NOT NULL CHECK (balans >= 0)
);
CREATE TABLE amaliyot (
  id SERIAL PRIMARY KEY,
  hisob_id INTEGER NOT NULL REFERENCES hisob(id),
  summa NUMERIC(12,2) NOT NULL
);
INSERT INTO hisob VALUES (1, 'Ali Valiyev', 500000), (2, 'Laylo Rahimova', 200000);""",
        "solution_sql": """\
BEGIN;
UPDATE hisob SET balans = balans - 100000 WHERE id = 1;
INSERT INTO amaliyot (hisob_id, summa) VALUES (1, 100000);
COMMIT;""",
        "concurrent": True,
        "theory": """\
Tranzaksiya — bir butun sifatida bajariladigan buyruqlar guruhi: BEGIN ... COMMIT. Hammasi bajariladi yoki \
(ROLLBACK yoki xato bo'lsa) hech biri bajarilmaydi. Tranzaksiya xususiyatlari — ACID: atomarlik, izchillik, \
izolyatsiya, chidamlilik.

PostgreSQL'da standart izolyatsiya darajasi READ COMMITTED: har bir buyruq boshqa tranzaksiyalarning faqat \
COMMIT qilingan o'zgarishlarini ko'radi. Boshqa tranzaksiya o'zgartirayotgan qatorni yangilashga urinilsa, u \
COMMIT qilinguncha kutiladi (qator qulfi).

Yo'qolgan yangilanish (lost update): ikki tranzaksiya bir qiymatni o'qiydi, har biri o'qiganidan yangi \
qiymat hisoblab yozadi — birinchisining o'zgarishi yo'qoladi. Yechimlar:
- o'zgarishni bitta atomar buyruq bilan qilish: SET ustun = ustun - x — bunda qiymat qulf olingandan keyin \
o'qiladi;
- yoki avval qatorni qulflash: SELECT ... FOR UPDATE — ikkinchi tranzaksiya birinchisi tugaguncha kutadi.

Namuna (boshqa mavzu: layklar hisoblagichi):
```sql
CREATE TABLE post (id INTEGER PRIMARY KEY, layklar INTEGER NOT NULL);
INSERT INTO post VALUES (1, 0);
BEGIN;
UPDATE post SET layklar = layklar + 1 WHERE id = 1;   -- atomar: o'qish va yozish birga
COMMIT;
```""",
    },
    {
        "title": "Tranzaksiya 2. Oxirgi mahsulot: «tekshir, keyin bajar» poygasi",
        "description": f"""\
Omborda bitta smartfon qoldi (mahsulot id = 1, qoldiq = 1). Xaridor uni sotib olmoqda. Bitta tranzaksiyada:
- agar qoldiq 0 dan katta bo'lsa: «buyurtma» jadvaliga yozuv qo'shing (mahsulot_id = 1) va qoldiqni 1 ga \
kamaytiring;
- agar qoldiq 0 bo'lsa: hech narsa qilmang (xato ham bermang).

Ikki xaridor bir vaqtda oxirgi smartfonni olmoqchi. Faqat bittasi olishi kerak: oxirida 1 ta buyurtma va \
qoldiq 0 bo'lsin (ikki buyurtma yoki manfiy qoldiq — xato).

Maslahat: shartli INSERT uchun INSERT INTO ... SELECT ... WHERE (shart) ishlatiladi. Shart tekshirilgan paytdan \
yozilgunicha boshqa tranzaksiya qoldiqni o'zgartirib ulgurmasligi kerak.

{CONCURRENCY_NOTE}""",
        "setup_sql": """\
CREATE TABLE mahsulot (
  id INTEGER PRIMARY KEY,
  nomi VARCHAR(100) NOT NULL,
  qoldiq INTEGER NOT NULL
);
CREATE TABLE buyurtma (
  id SERIAL PRIMARY KEY,
  mahsulot_id INTEGER NOT NULL REFERENCES mahsulot(id)
);
INSERT INTO mahsulot VALUES (1, 'Smartfon', 1), (2, 'Quloqchin', 10);""",
        "solution_sql": """\
BEGIN;
SELECT qoldiq FROM mahsulot WHERE id = 1 FOR UPDATE;
INSERT INTO buyurtma (mahsulot_id) SELECT 1 WHERE (SELECT qoldiq FROM mahsulot WHERE id = 1) > 0;
UPDATE mahsulot SET qoldiq = qoldiq - 1 WHERE id = 1 AND qoldiq > 0;
COMMIT;""",
        "concurrent": True,
        "theory": """\
«Tekshir, keyin bajar» (check-then-act) poygasi: tranzaksiya shartni tekshiradi (qoldiq bormi, o'rin bo'shmi), \
keyin unga tayanib yozadi. Agar shartni tekshirish va yozish orasida boshqa tranzaksiya ham xuddi shu shartni \
tekshirsa, ikkalasi ham «ha» javobini oladi — natijada ortiqcha sotuv yoki ikki marta band qilingan o'rin.

READ COMMITTED darajasida oddiy SELECT qatorni qulflamaydi va boshqa tranzaksiyaning COMMIT qilinmagan \
o'zgarishini ko'rmaydi. Yechimlar:
- SELECT ... FOR UPDATE: tekshirishdan oldin qatorni qulflash. Ikkinchi tranzaksiya kutadi va birinchisi \
tugagach yangi qiymatni o'qiydi;
- yoki shartni yozuvning o'ziga qo'shish: UPDATE ... WHERE qoldiq > 0 — kutgandan keyin shart yangi qiymat \
bo'yicha qayta tekshiriladi. Natijaga bog'liq keyingi yozuv uchun UPDATE ... RETURNING va WITH dan foydalanish \
mumkin.

Namuna (boshqa mavzu: kinoteatr o'rindig'ini band qilish):
```sql
CREATE TABLE orindiq (id INTEGER PRIMARY KEY, band BOOLEAN NOT NULL);
INSERT INTO orindiq VALUES (7, false);
BEGIN;
SELECT band FROM orindiq WHERE id = 7 FOR UPDATE;      -- qator qulflandi
UPDATE orindiq SET band = true WHERE id = 7 AND NOT band;
COMMIT;
```""",
    },
]
