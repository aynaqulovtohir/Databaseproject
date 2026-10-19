"""Yaxlitlik cheklovlari bo'yicha tayyor laboratoriyalar (labs/probes.py).

Talaba tayyor jadvallarga cheklovlar qo'shadi. Tekshiruv har bir sinovni alohida tranzaksiyada bajaradi: hujumni
cheklov rad etishi, to'g'ri ma'lumotni qabul qilishi kerak. Yashirin sinovlar ko'rinadigan misolga moslab yozilgan
tor cheklovni (masalan, CHECK (nusxalar <> -1)) va faqat INSERT ni tekshiradigan trigger'ni ushlaydi.
"""

PROBES_NOTE = (
    "Kodingizdan keyin «Cheklovlar sinovlari» bo'limidagi har bir buyruq alohida bajariladi va orqaga qaytariladi. "
    "Jadvallarni qayta yaratmang va ma'lumotlarni o'chirmang: faqat cheklov qo'shing (ALTER TABLE ... ADD ..., "
    "SET NOT NULL yoki trigger)."
)

THEORY_BASICS = """\
Yaxlitlik cheklovi — bazaning o'zi tekshiradigan qoida. Ilova xato qilsa ham, noto'g'ri ma'lumot jadvalga tushmaydi.

NOT NULL — qiymat majburiy:
ALTER TABLE xodim ALTER COLUMN familiya SET NOT NULL;

UNIQUE — takrorlanmaydi (NULL qiymatlar bir-biriga teng hisoblanmaydi, shuning uchun bir nechta NULL bo'lishi mumkin):
ALTER TABLE xodim ADD CONSTRAINT xodim_pasport_unique UNIQUE (pasport);

CHECK — har bir qatordagi shart (NULL bo'lsa shart bajarilgan hisoblanadi):
ALTER TABLE xodim ADD CONSTRAINT xodim_maosh_check CHECK (maosh > 0);
ALTER TABLE xodim ADD CHECK (lavozim IN ('muhandis', 'texnik', 'rahbar'));

Cheklovga nom bering (CONSTRAINT nom): xato xabarida qaysi qoida buzilgani ko'rinadi.

Qoidaning o'ziga mos cheklov yozing, misolga emas: «narx musbat» — CHECK (narx > 0), «narx -5 emas» emas."""

THEORY_FK = """\
FOREIGN KEY — bog'liq jadvaldagi qiymat haqiqatan mavjud bo'lishi kerak (havola yaxlitligi):
ALTER TABLE ishchi ADD CONSTRAINT ishchi_bolim_fk FOREIGN KEY (bolim_id) REFERENCES bolim (id);

Endi mavjud bo'lmagan bo'limga ishchi qo'shib bo'lmaydi, ishchisi bor bo'limni o'chirib ham bo'lmaydi (standart:
ON DELETE NO ACTION). Boshqa variantlar: ON DELETE CASCADE — bog'liq qatorlar ham o'chadi, ON DELETE SET NULL —
havola bo'shatiladi. Qaysi biri to'g'riligini biznes qoidasi hal qiladi.

FOREIGN KEY ustuni NULL bo'lsa, tekshirilmaydi: havola majburiy bo'lsa, NOT NULL ham qo'shing.

Ruxsat etilgan qiymatlar ro'yxati:
ALTER TABLE ariza ADD CHECK (turi IN ('tatil', 'kasallik', 'xizmat_safari'));"""

THEORY_TRIGGER = """\
Ba'zi qoidalarni bitta qatorga qarab tekshirib bo'lmaydi (masalan, «bir xodimning oylik ish soati 200 dan oshmasin» —
bir nechta qator yig'indisi). Bunday qoida trigger bilan yoziladi:

CREATE FUNCTION soat_chegarasi() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (SELECT SUM(soat) FROM ish_vaqti WHERE xodim_id = NEW.xodim_id AND oy = NEW.oy) > 200 THEN
    RAISE EXCEPTION 'Oylik ish soati 200 dan oshmasin';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER soat_chegarasi AFTER INSERT OR UPDATE ON ish_vaqti
FOR EACH ROW EXECUTE FUNCTION soat_chegarasi();

AFTER trigger yangi qator jadvalga qo'shilgandan keyin ishlaydi: yig'indiga u ham kiradi. RAISE EXCEPTION
butun buyruqni bekor qiladi. UPDATE ni ham unutmang: mavjud qatorni o'zgartirib ham qoidani buzish mumkin.

Bir nechta ustun birgalikda takrorlanmasligi: UNIQUE (xodim_id, oy, kun)."""

LIBRARY_SETUP = """\
CREATE TABLE kitob (
  id INTEGER PRIMARY KEY,
  isbn VARCHAR(20),
  nomi VARCHAR(200),
  muallif VARCHAR(100),
  yil INTEGER,
  nusxalar INTEGER
);
INSERT INTO kitob VALUES
  (1, '978-9943-01-001-1', 'O''tkan kunlar', 'Abdulla Qodiriy', 1926, 5),
  (2, '978-9943-01-002-8', 'Mehrobdan chayon', 'Abdulla Qodiriy', 1929, 3);"""

SHOP_SETUP = """\
CREATE TABLE mijoz (id INTEGER PRIMARY KEY, ism VARCHAR(100) NOT NULL, email VARCHAR(100));
CREATE TABLE mahsulot (id INTEGER PRIMARY KEY, nomi VARCHAR(100) NOT NULL, narx NUMERIC(10, 2), qoldiq INTEGER);
CREATE TABLE buyurtma (
  id INTEGER PRIMARY KEY,
  mijoz_id INTEGER,
  mahsulot_id INTEGER,
  miqdor INTEGER,
  holat VARCHAR(20)
);
INSERT INTO mijoz VALUES (1, 'Ali', 'ali@pochta.uz'), (2, 'Laylo', 'laylo@pochta.uz');
INSERT INTO mahsulot VALUES (1, 'Daftar', 5000, 100), (2, 'Ruchka', 2000, 50);
INSERT INTO buyurtma VALUES (1, 1, 1, 3, 'yangi'), (2, 2, 2, 1, 'yetkazildi');"""

UNIVERSITY_SETUP = """\
CREATE TABLE talaba (id INTEGER PRIMARY KEY, ism VARCHAR(100) NOT NULL);
CREATE TABLE fan (id INTEGER PRIMARY KEY, nomi VARCHAR(100) NOT NULL, kredit INTEGER NOT NULL);
CREATE TABLE yozilish (
  talaba_id INTEGER NOT NULL REFERENCES talaba (id),
  fan_id INTEGER NOT NULL REFERENCES fan (id),
  semestr INTEGER NOT NULL,
  baho INTEGER
);
INSERT INTO talaba VALUES (1, 'Aziz'), (2, 'Malika');
INSERT INTO fan VALUES
  (1, 'Ma''lumotlar bazasi', 6), (2, 'Algoritmlar', 6), (3, 'Fizika', 8), (4, 'Ingliz tili', 4),
  (5, 'Falsafa', 4), (6, 'Diplom ishi', 12), (7, 'Tarix', 2);
INSERT INTO yozilish VALUES (1, 1, 1, NULL), (1, 2, 1, 85), (1, 3, 1, NULL), (1, 6, 2, NULL), (2, 1, 1, 92);"""

INTEGRITY_LABS = [
    {
        "title": "Cheklovlar 1. Kutubxona: NOT NULL, UNIQUE va CHECK",
        "description": f"""\
Kutubxona «kitob» jadvalida hozir hech qanday qoida yo'q: nomsiz kitob, takror ISBN yoki manfiy nusxalar soni \
kiritilib ketishi mumkin. Quyidagi qoidalarni cheklovlar bilan bazaning o'ziga yuklang:

1. Kitob nomi va muallifi majburiy.
2. ISBN takrorlanmaydi (lekin eski qo'lyozmalarda ISBN bo'lmasligi mumkin).
3. Nusxalar soni manfiy bo'lmaydi (0 — hammasi berilgan, bu to'g'ri holat).
4. Nashr yili 1450 dan (kitob bosish ixtiro qilingan) 2100 gacha.

{PROBES_NOTE}""",
        "setup_sql": LIBRARY_SETUP,
        "solution_sql": """\
ALTER TABLE kitob ALTER COLUMN nomi SET NOT NULL;
ALTER TABLE kitob ALTER COLUMN muallif SET NOT NULL;
ALTER TABLE kitob ADD CONSTRAINT kitob_isbn_unique UNIQUE (isbn);
ALTER TABLE kitob ADD CONSTRAINT kitob_nusxalar_check CHECK (nusxalar >= 0);
ALTER TABLE kitob ADD CONSTRAINT kitob_yil_check CHECK (yil BETWEEN 1450 AND 2100);""",
        "probes": [
            {"id": "nomsiz", "title": "Nomsiz kitob", "kind": "attack",
             "sql": "INSERT INTO kitob VALUES (3, '978-9943-01-003-5', NULL, 'Cho''lpon', 1934, 2)"},
            {"id": "muallifsiz", "title": "Muallifsiz kitob", "kind": "attack",
             "sql": "INSERT INTO kitob VALUES (4, '978-9943-01-004-2', 'Kecha va kunduz', NULL, 1936, 1)"},
            {"id": "isbn", "title": "Takror ISBN", "kind": "attack",
             "sql": "INSERT INTO kitob VALUES (5, '978-9943-01-001-1', 'Boshqa kitob', 'Noma''lum', 2000, 1)"},
            {"id": "manfiy", "title": "Nusxalar soni manfiy", "kind": "attack",
             "sql": "UPDATE kitob SET nusxalar = -1 WHERE id = 1"},
            {"id": "kelajak", "title": "2500-yilda nashr etilgan kitob", "kind": "attack",
             "sql": "INSERT INTO kitob VALUES (6, '978-9943-01-006-6', 'Kelajak', 'Muallif', 2500, 1)"},
            {"id": "yangi", "title": "Yangi kitob qo'shish", "kind": "valid",
             "sql": "INSERT INTO kitob VALUES (7, '978-9943-01-007-3', 'Kecha va kunduz', 'Cho''lpon', 1936, 4)"},
            {"id": "nol", "title": "Hamma nusxalar berildi (0 ta)", "kind": "valid",
             "sql": "UPDATE kitob SET nusxalar = 0 WHERE id = 2"},
            {"id": "qolyozma", "title": "ISBNsiz qo'lyozmalar", "kind": "valid",
             "sql": "INSERT INTO kitob VALUES (8, NULL, 'Qo''lyozma 1', 'Noma''lum', 1890, 1), "
                    "(9, NULL, 'Qo''lyozma 2', 'Noma''lum', 1895, 1)"},
            {"id": "y-manfiy", "title": "Nusxalar soni -10 (boshqa kitob)", "kind": "attack", "hidden": True,
             "sql": "UPDATE kitob SET nusxalar = -10 WHERE id = 2"},
            {"id": "y-qadimgi", "title": "1200-yilgi kitob", "kind": "attack", "hidden": True,
             "sql": "INSERT INTO kitob VALUES (10, NULL, 'Qadimgi', 'Noma''lum', 1200, 1)"},
            {"id": "y-xamsa", "title": "1483-yilgi kitob (chegara ichida)", "kind": "valid", "hidden": True,
             "sql": "INSERT INTO kitob VALUES (11, '978-9943-01-011-0', 'Xamsa', 'Alisher Navoiy', 1483, 2)"},
        ],
        "theory": THEORY_BASICS,
        "level": 2,
    },
    {
        "title": "Cheklovlar 2. Onlayn do'kon: FOREIGN KEY va ruxsat etilgan qiymatlar",
        "description": f"""\
Onlayn do'kon bazasida uchta jadval bor: mijoz, mahsulot va buyurtma. Hozir buyurtma mavjud bo'lmagan mijozga \
yozilishi, mahsulot bepul yoki noma'lum holatda bo'lishi mumkin. Qoidalar:

1. Buyurtma mavjud mijoz va mavjud mahsulotga tegishli; ikkalasi ham majburiy.
2. Buyurtmasi bor mijozni o'chirib bo'lmaydi (buyurtmalar tarixi yo'qolmasin). Buyurtmasi yo'q mahsulotni o'chirish mumkin.
3. Mahsulot narxi musbat, ombordagi qoldiq manfiy emas.
4. Buyurtma miqdori musbat.
5. Buyurtma holati faqat: yangi, yuborildi, yetkazildi, bekor.
6. Mijoz emaili takrorlanmaydi (email ko'rsatilmasligi mumkin).

{PROBES_NOTE}""",
        "setup_sql": SHOP_SETUP,
        "solution_sql": """\
ALTER TABLE buyurtma ALTER COLUMN mijoz_id SET NOT NULL;
ALTER TABLE buyurtma ALTER COLUMN mahsulot_id SET NOT NULL;
ALTER TABLE buyurtma ADD CONSTRAINT buyurtma_mijoz_fk FOREIGN KEY (mijoz_id) REFERENCES mijoz (id);
ALTER TABLE buyurtma ADD CONSTRAINT buyurtma_mahsulot_fk FOREIGN KEY (mahsulot_id) REFERENCES mahsulot (id);
ALTER TABLE mahsulot ADD CONSTRAINT mahsulot_narx_check CHECK (narx > 0);
ALTER TABLE mahsulot ADD CONSTRAINT mahsulot_qoldiq_check CHECK (qoldiq >= 0);
ALTER TABLE buyurtma ADD CONSTRAINT buyurtma_miqdor_check CHECK (miqdor > 0);
ALTER TABLE buyurtma ADD CONSTRAINT buyurtma_holat_check CHECK (holat IN ('yangi', 'yuborildi', 'yetkazildi', 'bekor'));
ALTER TABLE mijoz ADD CONSTRAINT mijoz_email_unique UNIQUE (email);""",
        "probes": [
            {"id": "yoq-mijoz", "title": "Mavjud bo'lmagan mijozga buyurtma", "kind": "attack",
             "sql": "INSERT INTO buyurtma VALUES (3, 99, 1, 1, 'yangi')"},
            {"id": "mijozsiz", "title": "Mijozi ko'rsatilmagan buyurtma", "kind": "attack",
             "sql": "INSERT INTO buyurtma VALUES (4, NULL, 1, 1, 'yangi')"},
            {"id": "ochirish", "title": "Buyurtmasi bor mijozni o'chirish", "kind": "attack",
             "sql": "DELETE FROM mijoz WHERE id = 1"},
            {"id": "bepul", "title": "Bepul mahsulot", "kind": "attack",
             "sql": "UPDATE mahsulot SET narx = 0 WHERE id = 1"},
            {"id": "holat", "title": "Noma'lum holat", "kind": "attack",
             "sql": "INSERT INTO buyurtma VALUES (5, 1, 2, 1, 'yo''qolgan')"},
            {"id": "email", "title": "Takror email", "kind": "attack",
             "sql": "INSERT INTO mijoz VALUES (3, 'Vali', 'ali@pochta.uz')"},
            {"id": "yangi", "title": "Yangi buyurtma", "kind": "valid",
             "sql": "INSERT INTO buyurtma VALUES (6, 2, 1, 2, 'yangi')"},
            {"id": "yuborish", "title": "Buyurtma yuborildi", "kind": "valid",
             "sql": "UPDATE buyurtma SET holat = 'yuborildi' WHERE id = 1"},
            {"id": "mahsulot-ochirish", "title": "Buyurtmasi yo'q mahsulotni o'chirish", "kind": "valid",
             "sql": "INSERT INTO mahsulot VALUES (3, 'Qalam', 1500, 10);\nDELETE FROM mahsulot WHERE id = 3"},
            {"id": "y-miqdor", "title": "Miqdori 0 bo'lgan buyurtma", "kind": "attack", "hidden": True,
             "sql": "INSERT INTO buyurtma VALUES (7, 1, 1, 0, 'yangi')"},
            {"id": "y-qoldiq", "title": "Qoldiqni manfiyga tushirish", "kind": "attack", "hidden": True,
             "sql": "UPDATE mahsulot SET qoldiq = qoldiq - 500 WHERE id = 2"},
            {"id": "y-mahsulot", "title": "Buyurtmani yo'q mahsulotga o'zgartirish", "kind": "attack", "hidden": True,
             "sql": "UPDATE buyurtma SET mahsulot_id = 42 WHERE id = 2"},
            {"id": "y-emailsiz", "title": "Emailsiz ikki mijoz", "kind": "valid", "hidden": True,
             "sql": "INSERT INTO mijoz VALUES (4, 'Sardor', NULL), (5, 'Dilnoza', NULL)"},
        ],
        "theory": THEORY_FK,
        "level": 3,
    },
    {
        "title": "Cheklovlar 3. Universitet: bir nechta qatorga bog'liq qoida (trigger)",
        "description": f"""\
Talabalar fanlarga yoziladi («yozilish» jadvali). Qoidalar:

1. Baho hali qo'yilmagan bo'lishi (NULL) yoki 0 dan 100 gacha bo'ladi.
2. Talaba bir semestrda bitta fanga faqat bir marta yoziladi.
3. Semestr 1 dan 8 gacha.
4. Talaba bir semestrda jami 30 kreditdan ortiq fanga yozila olmaydi (aynan 30 — mumkin). Bu qoidani bitta qatorga \
qarab tekshirib bo'lmaydi: trigger yozing. Yozilishni boshqa semestrga ko'chirish (UPDATE) ham qoidani buzmasin.

{PROBES_NOTE}""",
        "setup_sql": UNIVERSITY_SETUP,
        "solution_sql": """\
ALTER TABLE yozilish ADD CONSTRAINT yozilish_baho_check CHECK (baho BETWEEN 0 AND 100);
ALTER TABLE yozilish ADD CONSTRAINT yozilish_unique UNIQUE (talaba_id, fan_id, semestr);
ALTER TABLE yozilish ADD CONSTRAINT yozilish_semestr_check CHECK (semestr BETWEEN 1 AND 8);

CREATE FUNCTION kredit_chegarasi() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (SELECT SUM(f.kredit) FROM yozilish y JOIN fan f ON f.id = y.fan_id
      WHERE y.talaba_id = NEW.talaba_id AND y.semestr = NEW.semestr) > 30 THEN
    RAISE EXCEPTION 'Semestrda 30 kreditdan ortiq fanga yozilib bo''lmaydi';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER kredit_chegarasi AFTER INSERT OR UPDATE ON yozilish
FOR EACH ROW EXECUTE FUNCTION kredit_chegarasi();""",
        "probes": [
            {"id": "baho", "title": "Baho 120", "kind": "attack",
             "sql": "UPDATE yozilish SET baho = 120 WHERE talaba_id = 1 AND fan_id = 2"},
            {"id": "takror", "title": "Bir fanga ikki marta yozilish", "kind": "attack",
             "sql": "INSERT INTO yozilish VALUES (2, 1, 1, NULL)"},
            {"id": "semestr", "title": "9-semestr", "kind": "attack",
             "sql": "INSERT INTO yozilish VALUES (2, 2, 9, NULL)"},
            {"id": "kredit", "title": "Semestrda 32 kredit (20 + Diplom ishi 12)", "kind": "attack",
             "sql": "INSERT INTO yozilish VALUES (1, 6, 1, NULL)"},
            {"id": "chegara", "title": "Aynan 30 kredit", "kind": "valid",
             "sql": "INSERT INTO yozilish VALUES (1, 4, 1, NULL), (1, 5, 1, NULL), (1, 7, 1, NULL)"},
            {"id": "baho-qoyish", "title": "Baho qo'yish", "kind": "valid",
             "sql": "UPDATE yozilish SET baho = 100 WHERE talaba_id = 1 AND fan_id = 1"},
            {"id": "boshqa-semestr", "title": "Boshqa semestrga yozilish", "kind": "valid",
             "sql": "INSERT INTO yozilish VALUES (2, 6, 2, NULL)"},
            {"id": "y-kochirish", "title": "Diplom ishini 1-semestrga ko'chirish (UPDATE, 32 kredit)", "kind": "attack", "hidden": True,
             "sql": "UPDATE yozilish SET semestr = 1 WHERE talaba_id = 1 AND fan_id = 6"},
            {"id": "y-manfiy", "title": "Manfiy baho", "kind": "attack", "hidden": True,
             "sql": "INSERT INTO yozilish VALUES (2, 3, 1, -5)"},
            {"id": "y-nol", "title": "0-semestr", "kind": "attack", "hidden": True,
             "sql": "INSERT INTO yozilish VALUES (2, 4, 0, NULL)"},
            {"id": "y-bahosiz", "title": "Bahosiz yozilish", "kind": "valid", "hidden": True,
             "sql": "INSERT INTO yozilish VALUES (2, 4, 1, NULL)"},
        ],
        "theory": THEORY_TRIGGER,
        "level": 4,
    },
]
