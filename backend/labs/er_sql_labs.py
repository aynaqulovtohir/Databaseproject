"""ER → SQL: talabaga tayyor ER-model beriladi, u shu model bo'yicha jadvallarni yaratadi.

Diagrammada ustun turlari yo'q, shuning uchun ular shartda beriladi. Jadval va tashqi kalit nomlari
qoidasi ham shartda: tekshiruv jadvallarni nomlari bo'yicha solishtiradi. Talabaning o'zi hal qiladi:
tashqi kalit qaysi jadvalda turadi, M:N uchun oraliq jadval, asosiy kalitlar, NOT NULL va UNIQUE.

Mavzular (kurslar markazi, maktab) boshqa laboratoriyalardagidan farqli: biri ikkinchisining yechimini bermaydi.
"""

FK_NOTE = "Tashqi kalitlarga ON DELETE / ON UPDATE amallarini qo'shmang."
NO_SELECT_NOTE = "Kod oxirida SELECT yozish shart emas: tekshiruv yaratilgan jadvallarni solishtiradi."
NAMING_NOTE = """\
Nomlash qoidalari:
- Jadval nomi — obyekt nomi kichik harflar bilan, apostrofsiz (O'qituvchi → oqituvchi).
- Tashqi kalit ustuni — bog'langan jadval nomi va _id (masalan, kurs_id), turi INTEGER.
- M:N bog'lanish uchun oraliq jadval nomi — ikki jadval nomi pastki chiziq bilan, diagrammadagi tartibda \
(masalan, a_b). Uning asosiy kaliti shu tartibdagi ikki tashqi kalitdan iborat."""


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


ER_SQL_LABS = [
    {
        "title": "ER → SQL 1. Kurslar markazi: 1:N bog'lanish",
        "description": f"""\
Berilgan ER-model bo'yicha jadvallarni yarating (ER-model shart ostida ko'rsatilgan).

Ustun turlari:
- id — SERIAL; ism, nomi — VARCHAR(100); telefon — VARCHAR(20); narx — NUMERIC(10,2)

Qo'shimcha qoidalar:
- Barcha atributlar majburiy.
- Ikki o'qituvchining telefoni bir xil bo'lmaydi.
- Har bir kursni aynan bitta o'qituvchi olib boradi.

O'zingiz hal qilasiz: tashqi kalit qaysi jadvalda bo'ladi va qanday cheklovlar kerak.

{NAMING_NOTE}

{FK_NOTE}
{NO_SELECT_NOTE}""",
        "given_diagram": {
            "entities": [
                _entity("oqituvchi", "O'qituvchi", 40, 80, "id", "ism", "telefon"),
                _entity("kurs", "Kurs", 440, 80, "id", "nomi", "narx"),
            ],
            "relationships": [_relationship("r1", "olib boradi", "oqituvchi", "1", "kurs", "N")],
        },
        "setup_sql": "",
        "solution_sql": """\
CREATE TABLE oqituvchi (
  id SERIAL PRIMARY KEY,
  ism VARCHAR(100) NOT NULL,
  telefon VARCHAR(20) NOT NULL UNIQUE
);
CREATE TABLE kurs (
  id SERIAL PRIMARY KEY,
  nomi VARCHAR(100) NOT NULL,
  narx NUMERIC(10,2) NOT NULL,
  oqituvchi_id INTEGER NOT NULL REFERENCES oqituvchi(id)
);""",
        "theory": """\
ER-modeldan jadvallarga o'tish qoidalari:
1. Har bir obyekt — alohida jadval, uning atributlari — ustunlar, PK — asosiy kalit.
2. 1:N bog'lanish — «N» tomondagi jadvalga «1» tomonning asosiy kaliti tashqi kalit sifatida qo'shiladi.
3. Bog'lanish majburiy bo'lsa (har bir yozuv albatta bog'langan), tashqi kalit ustuniga NOT NULL qo'yiladi.

Tashqi kalit «1» tomonga qo'yilmaydi: bitta katakka ko'p qiymat sig'maydi.

Namuna (boshqa model: sport zali). Murabbiy (id, ism) 1 — N Mashg'ulot (id, nomi, vaqt):
```sql
CREATE TABLE murabbiy (
  id SERIAL PRIMARY KEY,
  ism VARCHAR(100) NOT NULL
);
CREATE TABLE mashgulot (
  id SERIAL PRIMARY KEY,
  nomi VARCHAR(100) NOT NULL,
  vaqt TIME NOT NULL,
  murabbiy_id INTEGER NOT NULL REFERENCES murabbiy(id)   -- «N» tomonda
);
```""",
    },
    {
        "title": "ER → SQL 2. Kurslar markazi: M:N bog'lanish",
        "description": f"""\
Berilgan ER-model bo'yicha jadvallarni yarating (ER-model shart ostida ko'rsatilgan).

Ustun turlari:
- id — SERIAL; manzil — VARCHAR(200); nomi, ism — VARCHAR(100); telefon — VARCHAR(20)

Qo'shimcha qoidalar:
- Barcha atributlar majburiy.
- Ikki tinglovchining telefoni bir xil bo'lmaydi.
- Har bir kurs aynan bitta filialda o'tadi.
- Tinglovchi bir nechta kursga yozilishi, kursga esa ko'p tinglovchi yozilishi mumkin; bitta tinglovchi \
bitta kursga ikki marta yozilmaydi.

O'zingiz hal qilasiz: qaysi jadvallarda tashqi kalit bo'ladi, M:N bog'lanish qanday ifodalanadi va qanday \
cheklovlar kerak.

{NAMING_NOTE}

{FK_NOTE}
{NO_SELECT_NOTE}""",
        "given_diagram": {
            "entities": [
                _entity("filial", "Filial", 40, 60, "id", "manzil"),
                _entity("kurs", "Kurs", 400, 60, "id", "nomi"),
                _entity("tinglovchi", "Tinglovchi", 400, 300, "id", "ism", "telefon"),
            ],
            "relationships": [
                _relationship("r1", "o'tadi", "filial", "1", "kurs", "N"),
                _relationship("r2", "yoziladi", "tinglovchi", "N", "kurs", "N"),
            ],
        },
        "setup_sql": "",
        "solution_sql": """\
CREATE TABLE filial (
  id SERIAL PRIMARY KEY,
  manzil VARCHAR(200) NOT NULL
);
CREATE TABLE kurs (
  id SERIAL PRIMARY KEY,
  nomi VARCHAR(100) NOT NULL,
  filial_id INTEGER NOT NULL REFERENCES filial(id)
);
CREATE TABLE tinglovchi (
  id SERIAL PRIMARY KEY,
  ism VARCHAR(100) NOT NULL,
  telefon VARCHAR(20) NOT NULL UNIQUE
);
CREATE TABLE tinglovchi_kurs (
  tinglovchi_id INTEGER NOT NULL REFERENCES tinglovchi(id),
  kurs_id INTEGER NOT NULL REFERENCES kurs(id),
  PRIMARY KEY (tinglovchi_id, kurs_id)
);""",
        "theory": """\
M:N bog'lanishni ikki jadvalning birortasiga tashqi kalit qo'shib ifodalab bo'lmaydi: ikkala tomonda ham «ko'p». \
Shuning uchun alohida oraliq (bog'lovchi) jadval yaratiladi:
- unda ikkala obyektga ishora qiluvchi ikki tashqi kalit bo'ladi;
- asosiy kaliti shu ikki ustundan iborat tarkibli kalit — bitta juftlik ikki marta yozilmaydi;
- ikkala tashqi kalit ham NOT NULL (yarim juftlik ma'nosiz).

Jadvallarni to'g'ri tartibda yarating: avval boshqalar ishora qiladigan jadvallar, oraliq jadval oxirida.

Namuna (boshqa model: sport zali). A'zo (id, ism) N — N Mashg'ulot (id, nomi), bog'lanish «qatnashadi»:
```sql
CREATE TABLE azo (id SERIAL PRIMARY KEY, ism VARCHAR(100) NOT NULL);
CREATE TABLE mashgulot (id SERIAL PRIMARY KEY, nomi VARCHAR(100) NOT NULL);
CREATE TABLE azo_mashgulot (
  azo_id INTEGER NOT NULL REFERENCES azo(id),
  mashgulot_id INTEGER NOT NULL REFERENCES mashgulot(id),
  PRIMARY KEY (azo_id, mashgulot_id)
);
```""",
    },
    {
        "title": "ER → SQL 3. Maktab: 1:1, 1:N va hodisa-obyekt",
        "description": f"""\
Berilgan ER-model bo'yicha jadvallarni yarating (ER-model shart ostida ko'rsatilgan).

Ustun turlari:
- id — SERIAL; nomi (maktab), ism — VARCHAR(100); nomi (sinf) — VARCHAR(10); raqam — VARCHAR(10); \
qavat — INTEGER; sana — DATE

Qo'shimcha qoidalar:
- Barcha atributlar majburiy. Ikki maktabning nomi bir xil bo'lmaydi.
- Har bir o'qituvchi aynan bitta maktabda ishlaydi; har bir sinf aynan bitta maktabga tegishli.
- Har bir dars aynan bitta o'qituvchi va aynan bitta sinfga tegishli.
- Kabinet bitta o'qituvchiga biriktiriladi, o'qituvchida ham ko'pi bilan bitta kabinet bo'ladi. Kabinet hali \
hech kimga biriktirilmagan bo'lishi mumkin. Bu 1:1 bog'lanish uchun tashqi kalit kabinet jadvalida \
(oqituvchi_id) turadi — uni qanday cheklov 1:N emas, aynan 1:1 qilishini o'zingiz hal qilasiz.

{NAMING_NOTE}

{FK_NOTE}
{NO_SELECT_NOTE}""",
        "given_diagram": {
            "entities": [
                _entity("maktab", "Maktab", 40, 40, "id", "nomi"),
                _entity("oqituvchi", "O'qituvchi", 440, 40, "id", "ism"),
                _entity("kabinet", "Kabinet", 840, 40, "raqam", "qavat"),
                _entity("sinf", "Sinf", 40, 320, "id", "nomi"),
                _entity("dars", "Dars", 440, 320, "id", "sana"),
            ],
            "relationships": [
                _relationship("r1", "ishlaydi", "oqituvchi", "N", "maktab", "1"),
                _relationship("r2", "biriktirilgan", "oqituvchi", "1", "kabinet", "1"),
                _relationship("r3", "tegishli", "sinf", "N", "maktab", "1"),
                _relationship("r4", "o'tadi", "oqituvchi", "1", "dars", "N"),
                _relationship("r5", "qatnashadi", "sinf", "1", "dars", "N"),
            ],
        },
        "setup_sql": "",
        "solution_sql": """\
CREATE TABLE maktab (
  id SERIAL PRIMARY KEY,
  nomi VARCHAR(100) NOT NULL UNIQUE
);
CREATE TABLE oqituvchi (
  id SERIAL PRIMARY KEY,
  ism VARCHAR(100) NOT NULL,
  maktab_id INTEGER NOT NULL REFERENCES maktab(id)
);
CREATE TABLE kabinet (
  raqam VARCHAR(10) PRIMARY KEY,
  qavat INTEGER NOT NULL,
  oqituvchi_id INTEGER UNIQUE REFERENCES oqituvchi(id)
);
CREATE TABLE sinf (
  id SERIAL PRIMARY KEY,
  nomi VARCHAR(10) NOT NULL,
  maktab_id INTEGER NOT NULL REFERENCES maktab(id)
);
CREATE TABLE dars (
  id SERIAL PRIMARY KEY,
  sana DATE NOT NULL,
  oqituvchi_id INTEGER NOT NULL REFERENCES oqituvchi(id),
  sinf_id INTEGER NOT NULL REFERENCES sinf(id)
);""",
        "theory": """\
1:1 bog'lanish jadvallarda tashqi kalit va UNIQUE bilan ifodalanadi: oddiy tashqi kalit bir xil qiymatni ko'p \
qatorda takrorlashga ruxsat beradi (bu 1:N), UNIQUE esa har bir qiymat ko'pi bilan bir marta uchrashini \
ta'minlaydi (1:1). Bog'lanish ixtiyoriy bo'lsa, NOT NULL qo'yilmaydi: UNIQUE ustunda bir nechta NULL bo'lishi mumkin.

Hodisa-obyekt (dars, ijara, to'lov) — o'z atributlari bor obyekt. U har bir qatnashchiga «N» tomondan bog'lanadi, \
shuning uchun uning jadvalida har bir qatnashchiga tashqi kalit bo'ladi.

Tabiiy asosiy kalit (raqam, ISBN) SERIAL emas, oddiy matn yoki son ustuni bo'ladi.

Namuna (boshqa model: sport zali). Murabbiy (id, ism) 1 — 1 Shkaf (raqam, joyi), shkaf hali bo'sh bo'lishi mumkin:
```sql
CREATE TABLE murabbiy (id SERIAL PRIMARY KEY, ism VARCHAR(100) NOT NULL);
CREATE TABLE shkaf (
  raqam VARCHAR(10) PRIMARY KEY,
  joyi VARCHAR(50) NOT NULL,
  murabbiy_id INTEGER UNIQUE REFERENCES murabbiy(id)   -- UNIQUE: bitta murabbiyga bitta shkaf
);
```""",
    },
]
