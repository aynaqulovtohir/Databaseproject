"""Xavfsizlik: qatorlar darajasida himoya (Row-Level Security) bo'yicha tayyor laboratoriyalar.

Ilova foydalanuvchini sessiya o'zgaruvchisi bilan bildiradi (SET LOCAL app.talaba_id = '2'), siyosat (POLICY) esa
har bir foydalanuvchiga faqat unga tegishli qatorlarni ko'rsatadi. Tekshiruv so'rovlari (labs/evolution.py) turli
foydalanuvchi nomidan o'qiydi va yozadi; bu so'rovlar orqaga qaytariladi. Qum qutida talaba jadvallar egasi: egaga RLS
faqat FORCE ROW LEVEL SECURITY bilan qo'llanadi — bu ham tekshiriladi.
"""

SECURITY_NOTE = (
    "Jadvallar va ma'lumotlarni o'zgartirmang, faqat himoya qo'shing. «Tekshiruv so'rovlari» foydalanuvchini "
    "SET LOCAL bilan almashtirib o'qiydi va yozadi; tekshiruv boshqa (yashirin) ma'lumotlarda ham takrorlanadi."
)

THEORY_RLS = """\
Qatorlar darajasida himoya (RLS): bitta jadvaldan har bir foydalanuvchi faqat o'ziga tegishli qatorlarni ko'radi. Qoida
ilovada emas, bazada — ilovada xato bo'lsa ham boshqaning ma'lumoti chiqib ketmaydi.

Ilova kim ishlayotganini sessiya o'zgaruvchisi bilan bildiradi (tranzaksiya oxirigacha amal qiladi):
SET LOCAL app.xodim_id = '7';

1. RLS ni yoqish. Jadval egasi uchun ham majburiy qilish (aks holda egasi hamma qatorni ko'radi):
ALTER TABLE ish_haqi ENABLE ROW LEVEL SECURITY;
ALTER TABLE ish_haqi FORCE ROW LEVEL SECURITY;

2. Siyosat (USING — qaysi qatorlar ko'rinadi va o'zgartiriladi):
CREATE POLICY ozi ON ish_haqi
USING (xodim_id = NULLIF(current_setting('app.xodim_id', true), '')::int);

current_setting(..., true) — o'zgaruvchi berilmagan bo'lsa xato o'rniga NULL yoki bo'sh satr qaytaradi; NULLIF bo'sh
satrni NULL ga aylantiradi (aks holda ''::int xato beradi). NULL bilan solishtirish hech qachon rost bo'lmaydi:
foydalanuvchi aniqlanmasa, hech narsa ko'rinmaydi — xavfsiz standart.

Bir nechta rol: shartni OR bilan birlashtiring yoki bir nechta siyosat yarating (ular OR bilan qo'shiladi):
CREATE POLICY rahbar ON ish_haqi USING (current_setting('app.rol', true) = 'rahbar');

RLS yoqilgan, lekin birorta siyosat bo'lmasa — hech kim hech narsa ko'rmaydi."""

GRADES_SETUP = """\
CREATE TABLE baho (
  talaba_id INTEGER NOT NULL,
  fan VARCHAR(50) NOT NULL,
  ball INTEGER NOT NULL
);
INSERT INTO baho VALUES
  (1, 'Matematika', 80), (1, 'Fizika', 90), (2, 'Matematika', 70), (2, 'Tarix', 65), (3, 'Fizika', 99);"""

GRADES_HIDDEN = """\
CREATE TABLE baho (
  talaba_id INTEGER NOT NULL,
  fan VARCHAR(50) NOT NULL,
  ball INTEGER NOT NULL
);
INSERT INTO baho VALUES (1, 'Kimyo', 55), (2, 'Kimyo', 100), (2, 'Biologiya', 88), (5, 'Tarix', 71);"""

CLINIC_SETUP = """\
CREATE TABLE qabul (
  id INTEGER PRIMARY KEY,
  shifokor_id INTEGER NOT NULL,
  bemor_id INTEGER NOT NULL,
  tashxis TEXT
);
INSERT INTO qabul VALUES
  (1, 1, 10, 'Gripp'), (2, 1, 11, 'Angina'), (3, 2, 10, 'Allergiya'), (4, 2, 12, NULL), (5, 3, 11, 'Bronxit');"""

CLINIC_HIDDEN = """\
CREATE TABLE qabul (
  id INTEGER PRIMARY KEY,
  shifokor_id INTEGER NOT NULL,
  bemor_id INTEGER NOT NULL,
  tashxis TEXT
);
INSERT INTO qabul VALUES (7, 2, 20, 'Gastrit'), (8, 1, 21, NULL), (9, 2, 21, 'Migren'), (11, 1, 20, 'Gripp');"""

SECURITY_LABS = [
    {
        "title": "Xavfsizlik 1. RLS: talaba faqat o'z baholarini ko'radi",
        "description": f"""\
Elektron kundalikda barcha baholar bitta «baho» jadvalida. Ilova talabani sessiya o'zgaruvchisi bilan bildiradi: \
SET LOCAL app.talaba_id = '2'. Bazaning o'zida qoidani yozing:

1. Talaba faqat o'z baholarini ko'radi.
2. Talaba boshqa talabaning bahosini o'zgartira olmaydi (UPDATE uni ko'rmaydi).
3. Talaba aniqlanmagan bo'lsa (o'zgaruvchi berilmagan yoki bo'sh), hech qanday baho ko'rinmaydi va xato chiqmaydi.

{SECURITY_NOTE}""",
        "setup_sql": GRADES_SETUP,
        "hidden_setup_sql": GRADES_HIDDEN,
        "solution_sql": """\
ALTER TABLE baho ENABLE ROW LEVEL SECURITY;
ALTER TABLE baho FORCE ROW LEVEL SECURITY;
CREATE POLICY talaba_ozi ON baho
USING (talaba_id = NULLIF(current_setting('app.talaba_id', true), '')::int);""",
        "check_queries": [
            {"id": "birinchi", "title": "1-talaba o'z baholarini ko'radi",
             "sql": "SET LOCAL app.talaba_id = '1';\nSELECT fan, ball FROM baho ORDER BY fan"},
            {"id": "ikkinchi", "title": "2-talaba o'z baholarini ko'radi",
             "sql": "SET LOCAL app.talaba_id = '2';\nSELECT talaba_id, fan, ball FROM baho ORDER BY fan"},
            {"id": "aniqlanmagan", "title": "Talaba aniqlanmagan — hech narsa ko'rinmaydi",
             "sql": "SELECT count(*) FROM baho"},
            {"id": "bosh", "title": "Bo'sh qiymat — hech narsa ko'rinmaydi, xato yo'q",
             "sql": "SET LOCAL app.talaba_id = '';\nSELECT count(*) FROM baho"},
            {"id": "ozgartirish", "title": "1-talaba hammaga 100 qo'yishga urinadi — 2-talabaning bahosi o'zgarmaydi",
             "sql": "SET LOCAL app.talaba_id = '1';\nUPDATE baho SET ball = 100;\n"
                    "SET LOCAL app.talaba_id = '2';\nSELECT fan, ball FROM baho ORDER BY fan"},
        ],
        "theory": THEORY_RLS,
        "topic": "security",
        "level": 3,
    },
    {
        "title": "Xavfsizlik 2. RLS: shifokor, bemor va bosh shifokor",
        "description": f"""\
Klinikada «qabul» jadvalidagi tashxislar maxfiy. Ilova foydalanuvchini ikki o'zgaruvchi bilan bildiradi: \
app.rol ('shifokor', 'bemor' yoki 'bosh_shifokor') va app.user_id. Qoidalar:

1. Shifokor faqat o'zi qabul qilgan yozuvlarni ko'radi va faqat ularni o'zgartiradi.
2. Bemor faqat o'z qabullarini ko'radi.
3. Bosh shifokor hamma yozuvni ko'radi.
4. Rol aniqlanmagan yoki noma'lum bo'lsa — hech narsa ko'rinmaydi.

{SECURITY_NOTE}""",
        "setup_sql": CLINIC_SETUP,
        "hidden_setup_sql": CLINIC_HIDDEN,
        "solution_sql": """\
ALTER TABLE qabul ENABLE ROW LEVEL SECURITY;
ALTER TABLE qabul FORCE ROW LEVEL SECURITY;
CREATE POLICY qabul_kirish ON qabul USING (
  CASE current_setting('app.rol', true)
    WHEN 'shifokor' THEN shifokor_id = NULLIF(current_setting('app.user_id', true), '')::int
    WHEN 'bemor' THEN bemor_id = NULLIF(current_setting('app.user_id', true), '')::int
    WHEN 'bosh_shifokor' THEN true
    ELSE false
  END
);""",
        "check_queries": [
            {"id": "shifokor", "title": "1-shifokor o'z qabullarini ko'radi",
             "sql": "SET LOCAL app.rol = 'shifokor';\nSET LOCAL app.user_id = '1';\nSELECT id, bemor_id, tashxis FROM qabul ORDER BY id"},
            {"id": "bemor", "title": "Bemor (10 yoki 20) o'z qabullarini ko'radi",
             "sql": "SET LOCAL app.rol = 'bemor';\nSET LOCAL app.user_id = '10';\nSELECT id, shifokor_id FROM qabul ORDER BY id;"},
            {"id": "bemor-21", "title": "Boshqa bemor (11 yoki 21)",
             "sql": "SET LOCAL app.rol = 'bemor';\nSET LOCAL app.user_id = '21';\nSELECT id FROM qabul ORDER BY id"},
            {"id": "bosh", "title": "Bosh shifokor hammasini ko'radi",
             "sql": "SET LOCAL app.rol = 'bosh_shifokor';\nSELECT count(*) FROM qabul"},
            {"id": "nomalum", "title": "Noma'lum rol — hech narsa ko'rinmaydi",
             "sql": "SET LOCAL app.rol = 'mehmon';\nSET LOCAL app.user_id = '1';\nSELECT count(*) FROM qabul"},
            {"id": "aniqlanmagan", "title": "Rol berilmagan — hech narsa ko'rinmaydi", "sql": "SELECT count(*) FROM qabul"},
            {"id": "yozish", "title": "1-shifokor hamma tashxisni o'zgartirishga urinadi — faqat o'ziniki o'zgaradi",
             "sql": "SET LOCAL app.rol = 'shifokor';\nSET LOCAL app.user_id = '1';\nUPDATE qabul SET tashxis = 'Sog''lom';\n"
                    "SET LOCAL app.rol = 'bosh_shifokor';\nSELECT id, tashxis FROM qabul ORDER BY id"},
        ],
        "theory": THEORY_RLS,
        "topic": "security",
        "level": 4,
    },
]
