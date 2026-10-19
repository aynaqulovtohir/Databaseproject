"""Teskari loyihalash bo'yicha tayyor laboratoriyalar: bazadan ER-diagrammaga (labs/reverse.py).

Talabaga tayyor baza (CREATE TABLE) beriladi, u shu bazaning ER-diagrammasini tiklaydi. Namunaviy diagramma
saqlashda (seed buyrug'ida va o'qituvchi oynasida) bazaning o'zidan hosil qilinadi, shuning uchun bu yerda yo'q.
"""

REVERSE_NOTE = """\
Diagrammani chizish qoidalari:
- Obyekt va atribut nomlarini jadval va ustun nomlaridek yozing (katta-kichik harf farqi yo'q).
- Har bir obyektda asosiy kalitni (PK) belgilang.
- Tashqi kalit (FK) ustunlarini atribut sifatida yozish shart emas: ularni bog'lanish ifodalaydi.
- Kardinallikni kalitlardan aniqlang: FOREIGN KEY bor jadval tomonida «N», havola qilingan jadval tomonida «1».
  Tashqi kalit UNIQUE bo'lsa — 1:1.
- Faqat ikkita tashqi kalitdan iborat oraliq jadvalni obyekt qilib emas, ko'p-ko'p (N — N) bog'lanish sifatida chizing.
  Oraliq jadvalda boshqa ustunlar ham bo'lsa (masalan, sana), u alohida obyekt bo'ladi."""

THEORY_REVERSE = """\
Teskari loyihalash (reverse engineering) — mavjud bazaning tuzilishidan uning konseptual modelini tiklash. Hujjatsiz
eski tizim bilan ishlaganda yoki bazani yangisiga ko'chirishdan oldin shunday qilinadi.

Qoidalar (boshqa misolda):

CREATE TABLE viloyat (id INTEGER PRIMARY KEY, nomi VARCHAR(50));
CREATE TABLE shahar (id INTEGER PRIMARY KEY, nomi VARCHAR(50), viloyat_id INTEGER REFERENCES viloyat (id));
CREATE TABLE hokim (id INTEGER PRIMARY KEY, fio VARCHAR(100), shahar_id INTEGER UNIQUE REFERENCES shahar (id));
CREATE TABLE festival (id INTEGER PRIMARY KEY, nomi VARCHAR(100));
CREATE TABLE shahar_festival (shahar_id INTEGER REFERENCES shahar (id), festival_id INTEGER REFERENCES festival (id),
  PRIMARY KEY (shahar_id, festival_id));

- viloyat, shahar, hokim, festival — obyektlar; ustunlari — atributlar; PRIMARY KEY — asosiy kalit.
- shahar.viloyat_id → viloyat: Shahar (N) — Viloyat (1). Bitta viloyatda ko'p shahar.
- hokim.shahar_id UNIQUE → shahar: Hokim (1) — Shahar (1). UNIQUE tufayli bitta shaharga bitta hokim.
- shahar_festival faqat ikki tashqi kalitdan iborat: Shahar (N) — Festival (N) bog'lanishi, obyekt emas.

O'z-o'ziga havola (masalan, xodim.rahbar_id → xodim) — obyektning o'zi bilan bog'lanishi: Xodim (N) — Xodim (1)."""

REVERSE_LABS = [
    {
        "kind": "er",
        "title": "Teskari loyihalash 1. Kafedra bazasi",
        "description": f"""\
Universitet kafedrasining bazasi berilgan (pastdagi «Berilgan baza»). Uning hujjati yo'qolgan: jadvallar va kalitlarga \
qarab ER-diagrammasini tiklang.

{REVERSE_NOTE}""",
        "setup_sql": """\
CREATE TABLE kafedra (
  id INTEGER PRIMARY KEY,
  nomi VARCHAR(100) NOT NULL,
  xona VARCHAR(10)
);
CREATE TABLE oqituvchi (
  id INTEGER PRIMARY KEY,
  fio VARCHAR(100) NOT NULL,
  unvon VARCHAR(50),
  kafedra_id INTEGER NOT NULL REFERENCES kafedra (id)
);
CREATE TABLE fan (
  id INTEGER PRIMARY KEY,
  nomi VARCHAR(100) NOT NULL,
  kredit INTEGER,
  oqituvchi_id INTEGER REFERENCES oqituvchi (id)
);""",
        "theory": THEORY_REVERSE,
        "level": 1,
    },
    {
        "kind": "er",
        "title": "Teskari loyihalash 2. Klinika bazasi",
        "description": f"""\
Xususiy klinika bazasi berilgan. Jadvallar va kalitlarga qarab ER-diagrammasini tiklang. E'tibor bering: qaysi \
jadval oraliq jadval (bog'lanish), qaysi biri o'z atributlari bor obyekt; qaysi tashqi kalit UNIQUE.

{REVERSE_NOTE}""",
        "setup_sql": """\
CREATE TABLE shifokor (
  id INTEGER PRIMARY KEY,
  fio VARCHAR(100) NOT NULL,
  telefon VARCHAR(20)
);
CREATE TABLE mutaxassislik (
  id INTEGER PRIMARY KEY,
  nomi VARCHAR(100) NOT NULL
);
CREATE TABLE shifokor_mutaxassislik (
  shifokor_id INTEGER REFERENCES shifokor (id),
  mutaxassislik_id INTEGER REFERENCES mutaxassislik (id),
  PRIMARY KEY (shifokor_id, mutaxassislik_id)
);
CREATE TABLE bemor (
  id INTEGER PRIMARY KEY,
  fio VARCHAR(100) NOT NULL,
  tugilgan_sana DATE
);
CREATE TABLE tibbiy_karta (
  id INTEGER PRIMARY KEY,
  qon_guruhi VARCHAR(5),
  allergiya TEXT,
  bemor_id INTEGER NOT NULL UNIQUE REFERENCES bemor (id)
);
CREATE TABLE qabul (
  id INTEGER PRIMARY KEY,
  sana TIMESTAMP NOT NULL,
  tashxis TEXT,
  shifokor_id INTEGER NOT NULL REFERENCES shifokor (id),
  bemor_id INTEGER NOT NULL REFERENCES bemor (id)
);""",
        "theory": THEORY_REVERSE,
        "level": 3,
    },
    {
        "kind": "er",
        "title": "Teskari loyihalash 3. Korxona bazasi",
        "description": f"""\
Korxona bazasi berilgan. Unda o'z-o'ziga havola (xodimning rahbari ham xodim) va bir juft jadval orasida ikkita \
turli bog'lanish bor (xodim bo'limda ishlaydi; bo'limni bitta xodim boshqaradi). ER-diagrammasini tiklang.

{REVERSE_NOTE}""",
        "setup_sql": """\
CREATE TABLE bolim (
  id INTEGER PRIMARY KEY,
  nomi VARCHAR(100) NOT NULL
);
CREATE TABLE xodim (
  id INTEGER PRIMARY KEY,
  fio VARCHAR(100) NOT NULL,
  maosh NUMERIC(12, 2),
  bolim_id INTEGER REFERENCES bolim (id),
  rahbar_id INTEGER REFERENCES xodim (id)
);
ALTER TABLE bolim ADD COLUMN boshliq_id INTEGER UNIQUE REFERENCES xodim (id);
CREATE TABLE loyiha (
  id INTEGER PRIMARY KEY,
  nomi VARCHAR(100) NOT NULL,
  muddat DATE
);
CREATE TABLE xodim_loyiha (
  xodim_id INTEGER REFERENCES xodim (id),
  loyiha_id INTEGER REFERENCES loyiha (id),
  PRIMARY KEY (xodim_id, loyiha_id)
);""",
        "theory": THEORY_REVERSE,
        "level": 4,
    },
]
