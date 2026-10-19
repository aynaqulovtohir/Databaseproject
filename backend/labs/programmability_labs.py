"""View, funksiya va trigger bo'yicha tayyor laboratoriyalar (tekshiruv: labs/evolution.py, check_queries).

Tekshiruv so'rovi bir nechta buyruqdan iborat: avval ma'lumot o'zgartiriladi (INSERT/UPDATE), keyin natija o'qiladi.
Shu bilan view haqiqatan view ekani (jadval nusxasi emas — yangi qator darhol ko'rinadi), funksiya istalgan
qiymatda ishlashi va trigger kerakli paytda (va faqat o'shanda) ishlashi tekshiriladi. Hammasi orqaga qaytariladi.
"""

PROGRAM_NOTE = (
    "Tayyor jadvallarni o'zgartirmang. «Tekshiruv so'rovlari» kodingizdan keyin bajariladi: ular ma'lumotni o'zgartirib "
    "ko'radi va natijani namunaviy yechimniki bilan solishtiradi. Tekshiruv boshqa (yashirin) ma'lumotlarda ham takrorlanadi."
)

THEORY_PROGRAM = """\
VIEW — saqlangan so'rov. U ma'lumotni nusxalamaydi: har safar o'qilganda jadvallardan qayta hisoblanadi.
CREATE VIEW bolim_maosh AS
SELECT b.nomi, count(x.id) AS xodimlar, round(avg(x.maosh), 2) AS ortacha_maosh
FROM bolim b LEFT JOIN xodim x ON x.bolim_id = b.id
GROUP BY b.id, b.nomi;
(CREATE TABLE ... AS SELECT esa bir martalik nusxa: keyingi o'zgarishlar unda ko'rinmaydi.)

Funksiya — nomi bilan chaqiriladigan hisob:
CREATE FUNCTION xodim_soliq(xodim_id INTEGER) RETURNS NUMERIC LANGUAGE sql AS $$
  SELECT COALESCE(SUM(maosh * 0.12), 0) FROM xodim WHERE id = xodim_id;
$$;
SELECT xodim_soliq(7);
COALESCE natija bo'lmaganda (NULL) o'rniga 0 qaytaradi.

Trigger — jadvaldagi o'zgarishga avtomatik javob. OLD — o'zgarishdan oldingi qator, NEW — keyingisi:
CREATE FUNCTION maosh_jurnali() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.maosh IS DISTINCT FROM OLD.maosh THEN
    INSERT INTO maosh_tarixi (xodim_id, eski, yangi) VALUES (OLD.id, OLD.maosh, NEW.maosh);
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER maosh_jurnali AFTER UPDATE ON xodim FOR EACH ROW EXECUTE FUNCTION maosh_jurnali();
IS DISTINCT FROM — NULL qiymatlarni ham to'g'ri solishtiradi (= dan farqli)."""

SCHOOL_SETUP = """\
CREATE TABLE talaba (id INTEGER PRIMARY KEY, ism VARCHAR(100) NOT NULL);
CREATE TABLE baho (talaba_id INTEGER NOT NULL REFERENCES talaba (id), fan VARCHAR(50) NOT NULL, ball INTEGER NOT NULL);
INSERT INTO talaba VALUES (1, 'Aziz'), (2, 'Malika'), (3, 'Sardor');
INSERT INTO baho VALUES (1, 'Matematika', 80), (1, 'Fizika', 90), (2, 'Matematika', 95), (2, 'Tarix', 72);"""

SCHOOL_HIDDEN = """\
CREATE TABLE talaba (id INTEGER PRIMARY KEY, ism VARCHAR(100) NOT NULL);
CREATE TABLE baho (talaba_id INTEGER NOT NULL REFERENCES talaba (id), fan VARCHAR(50) NOT NULL, ball INTEGER NOT NULL);
INSERT INTO talaba VALUES (4, 'Dilnoza'), (6, 'Jasur'), (9, 'Bobur');
INSERT INTO baho VALUES (4, 'Kimyo', 61), (4, 'Kimyo', 70), (6, 'Fizika', 100), (9, 'Tarix', 55), (9, 'Tarix', 56);"""

ORDERS_SETUP = """\
CREATE TABLE buyurtma (id INTEGER PRIMARY KEY, mijoz VARCHAR(100) NOT NULL);
CREATE TABLE buyurtma_qator (
  buyurtma_id INTEGER NOT NULL REFERENCES buyurtma (id),
  mahsulot VARCHAR(100) NOT NULL,
  narx NUMERIC(10, 2) NOT NULL,
  miqdor INTEGER NOT NULL
);
INSERT INTO buyurtma VALUES (1, 'Ali'), (2, 'Laylo'), (3, 'Vali');
INSERT INTO buyurtma_qator VALUES (1, 'Daftar', 5000, 3), (1, 'Ruchka', 2000, 2), (2, 'Kitob', 45000, 1);"""

ORDERS_HIDDEN = """\
CREATE TABLE buyurtma (id INTEGER PRIMARY KEY, mijoz VARCHAR(100) NOT NULL);
CREATE TABLE buyurtma_qator (
  buyurtma_id INTEGER NOT NULL REFERENCES buyurtma (id),
  mahsulot VARCHAR(100) NOT NULL,
  narx NUMERIC(10, 2) NOT NULL,
  miqdor INTEGER NOT NULL
);
INSERT INTO buyurtma VALUES (7, 'Sardor'), (8, 'Nodira');
INSERT INTO buyurtma_qator VALUES (7, 'Qalam', 1500.50, 4), (7, 'Atlas', 30000, 1);"""

PRICES_SETUP = """\
CREATE TABLE mahsulot (id INTEGER PRIMARY KEY, nomi VARCHAR(100) NOT NULL, narx NUMERIC(10, 2) NOT NULL);
INSERT INTO mahsulot VALUES (1, 'Daftar', 5000), (2, 'Ruchka', 2000), (3, 'Kitob', 45000);"""

PRICES_HIDDEN = """\
CREATE TABLE mahsulot (id INTEGER PRIMARY KEY, nomi VARCHAR(100) NOT NULL, narx NUMERIC(10, 2) NOT NULL);
INSERT INTO mahsulot VALUES (1, 'Qalam', 1500), (2, 'Atlas', 30000), (5, 'Globus', 120000);"""

PROGRAMMABILITY_LABS = [
    {
        "title": "Dasturlash 1. VIEW: talabalar reytingi",
        "description": f"""\
O'quv bo'limi talabalar reytingini tez-tez so'raydi. Har safar uzun so'rov yozmaslik uchun «reyting» nomli VIEW yarating. \
Ustunlari (shu tartibda):
- ism — talaba ismi;
- fanlar — talaba baho olgan yozuvlar soni;
- ortacha — o'rtacha ball, 2 xonagacha yaxlitlangan (round(..., 2)).

Hali bahosi yo'q talaba ham ko'rinsin: fanlar = 0, ortacha = NULL. Yangi baho qo'shilsa, reyting darhol yangilanishi kerak.

{PROGRAM_NOTE}""",
        "setup_sql": SCHOOL_SETUP,
        "hidden_setup_sql": SCHOOL_HIDDEN,
        "solution_sql": """\
CREATE VIEW reyting AS
SELECT t.ism, count(b.ball) AS fanlar, round(avg(b.ball), 2) AS ortacha
FROM talaba t LEFT JOIN baho b ON b.talaba_id = t.id
GROUP BY t.id, t.ism;""",
        "check_queries": [
            {"id": "reyting", "title": "Reyting (o'rtacha ball bo'yicha)",
             "sql": "SELECT ism, fanlar, ortacha FROM reyting ORDER BY ortacha DESC NULLS LAST, ism"},
            {"id": "yangilanish", "title": "Yangi baho qo'shilgach reyting yangilanadi",
             "sql": "INSERT INTO baho SELECT id, 'Ingliz tili', 100 FROM talaba;\n"
                    "SELECT ism, fanlar, ortacha FROM reyting ORDER BY ism"},
        ],
        "theory": THEORY_PROGRAM,
        "topic": "programmability",
        "level": 2,
    },
    {
        "title": "Dasturlash 2. Funksiya: buyurtma summasi",
        "description": f"""\
Kassa dasturi buyurtma summasini ko'p joyda hisoblaydi. «buyurtma_summasi(buyurtma_id INTEGER) RETURNS NUMERIC» \
funksiyasini yozing: buyurtmadagi barcha qatorlar uchun narx × miqdor yig'indisi. Qatori yo'q (yoki mavjud bo'lmagan) \
buyurtma uchun 0 qaytarsin, NULL emas.

{PROGRAM_NOTE}""",
        "setup_sql": ORDERS_SETUP,
        "hidden_setup_sql": ORDERS_HIDDEN,
        "solution_sql": """\
CREATE FUNCTION buyurtma_summasi(buyurtma_id INTEGER) RETURNS NUMERIC LANGUAGE sql AS $$
  SELECT COALESCE(SUM(q.narx * q.miqdor), 0) FROM buyurtma_qator q WHERE q.buyurtma_id = $1;
$$;""",
        "check_queries": [
            {"id": "barchasi", "title": "Har bir buyurtma summasi",
             "sql": "SELECT id, buyurtma_summasi(id) FROM buyurtma ORDER BY id"},
            {"id": "yangi-qator", "title": "Qator qo'shilgach summa o'zgaradi",
             "sql": "INSERT INTO buyurtma_qator SELECT id, 'Sovg''a', 1000, 2 FROM buyurtma;\n"
                    "SELECT id, buyurtma_summasi(id) FROM buyurtma ORDER BY id"},
            {"id": "yoq", "title": "Mavjud bo'lmagan buyurtma", "sql": "SELECT buyurtma_summasi(-1)"},
        ],
        "theory": THEORY_PROGRAM,
        "topic": "programmability",
        "level": 3,
    },
    {
        "title": "Dasturlash 3. Trigger: narxlar tarixini saqlash",
        "description": f"""\
Soliq tekshiruvi uchun mahsulot narxi qachon va qanday o'zgargani saqlanishi kerak (tarixni saqlash).

1. «narx_tarixi» jadvalini yarating: mahsulot_id (INTEGER NOT NULL, «mahsulot» ga FOREIGN KEY), eski_narx va yangi_narx \
(NUMERIC(10, 2) NOT NULL), ozgargan (TIMESTAMP NOT NULL DEFAULT now()).
2. Trigger yozing: mahsulot narxi o'zgarganda tarixga bitta qator yozilsin. Faqat nomi o'zgarganda yoki narx avvalgi \
qiymatiga teng qilib yangilanganda yozilmasin.

{PROGRAM_NOTE}""",
        "setup_sql": PRICES_SETUP,
        "hidden_setup_sql": PRICES_HIDDEN,
        "solution_sql": """\
CREATE TABLE narx_tarixi (
  mahsulot_id INTEGER NOT NULL REFERENCES mahsulot (id),
  eski_narx NUMERIC(10, 2) NOT NULL,
  yangi_narx NUMERIC(10, 2) NOT NULL,
  ozgargan TIMESTAMP NOT NULL DEFAULT now()
);

CREATE FUNCTION narx_jurnali() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.narx IS DISTINCT FROM OLD.narx THEN
    INSERT INTO narx_tarixi (mahsulot_id, eski_narx, yangi_narx) VALUES (OLD.id, OLD.narx, NEW.narx);
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER narx_jurnali AFTER UPDATE ON mahsulot FOR EACH ROW EXECUTE FUNCTION narx_jurnali();""",
        "check_queries": [
            {"id": "ikki-marta", "title": "Narx ikki marta o'zgardi",
             "sql": "UPDATE mahsulot SET narx = narx + 500 WHERE id = (SELECT min(id) FROM mahsulot);\n"
                    "UPDATE mahsulot SET narx = narx * 2 WHERE id = (SELECT min(id) FROM mahsulot);\n"
                    "SELECT mahsulot_id, eski_narx, yangi_narx FROM narx_tarixi ORDER BY yangi_narx"},
            {"id": "hammasi", "title": "Barcha narxlar 10% oshdi",
             "sql": "UPDATE mahsulot SET narx = round(narx * 1.1, 2);\n"
                    "SELECT mahsulot_id, eski_narx, yangi_narx FROM narx_tarixi ORDER BY mahsulot_id"},
            {"id": "nom", "title": "Faqat nom o'zgardi — tarixga yozilmaydi",
             "sql": "UPDATE mahsulot SET nomi = nomi || ' (yangi)';\nSELECT count(*) FROM narx_tarixi"},
            {"id": "teng", "title": "Narx o'ziga teng qilib yangilandi — yozilmaydi",
             "sql": "UPDATE mahsulot SET narx = narx;\nSELECT count(*) FROM narx_tarixi"},
        ],
        "theory": THEORY_PROGRAM,
        "topic": "programmability",
        "level": 4,
    },
]
