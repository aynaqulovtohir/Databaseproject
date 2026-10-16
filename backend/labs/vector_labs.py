"""Vektorli qidiruv (pgvector) bo'yicha tayyor laboratoriyalar.

Haqiqiy embedding modeli ishlatilmaydi: vektorlar 3 o'lchamli va qo'lda tanlangan — shunda talaba masofani
qog'ozda ham hisoblab, natijani tushuna oladi. Kengaytma qum qutining "ext" sxemasida o'rnatilgan
(labs/sandbox.py), talaba vector turini va <->, <=> operatorlarini to'g'ridan-to'g'ri ishlatadi.
"""

THEORY = """\
Zamonaviy AI ilovalari matn, rasm yoki mahsulotni sonlar ro'yxati — vektor (embedding) ko'rinishida saqlaydi.
Ma'nosi yaqin narsalarning vektorlari ham yaqin bo'ladi. PostgreSQL'ning pgvector kengaytmasi:
- vector(n) — n o'lchamli vektor turi, qiymati matn sifatida yoziladi: '[0.1, 0.2, 0.3]';
- a <-> b — Evklid (L2) masofa: vektorlar uchlari orasidagi masofa, uzunlik ham hisobga olinadi;
- a <=> b — kosinus masofa (1 - kosinus o'xshashlik): faqat yo'nalishni solishtiradi. [1, 0] va [5, 0] ning
  kosinus masofasi 0, L2 masofasi esa 4 — qaysi biri kerakligi masalaga bog'liq;
- "eng yaqin k ta" so'rovi: ORDER BY masofa LIMIT k.
Katta jadvalda tezlik uchun maxsus indeks yaratiladi: CREATE INDEX ... USING hnsw (ustun vector_l2_ops).

Namuna (boshqa mavzu): eng yaqin 2 ta shahar (koordinatalar vektor sifatida).
```
CREATE TABLE shahar (nomi TEXT, joy vector(2));
INSERT INTO shahar VALUES ('A', '[0, 0]'), ('B', '[3, 4]'), ('C', '[1, 1]');
SELECT nomi, joy <-> '[0, 1]' AS masofa
FROM shahar
ORDER BY joy <-> '[0, 1]'
LIMIT 2;
```"""

SETUP = """\
CREATE TABLE maqola (
  id INTEGER PRIMARY KEY,
  sarlavha VARCHAR(100) NOT NULL,
  mavzu VARCHAR(30) NOT NULL,
  embedding vector(3) NOT NULL
);
INSERT INTO maqola VALUES
  (1, 'SQL JOIN turlari', 'baza', '[0.9, 0.1, 0.0]'),
  (2, 'Indekslar qanday ishlaydi', 'baza', '[0.8, 0.3, 0.1]'),
  (3, 'Futbol: yarim final', 'sport', '[0.0, 0.9, 0.2]'),
  (4, 'Normallashtirish', 'baza', '[0.7, 0.0, 0.3]'),
  (5, 'Shaxmat olimpiadasi', 'sport', '[0.2, 0.8, 0.1]'),
  (6, 'Palov retsepti', 'oshxona', '[0.1, 0.1, 0.9]'),
  (7, 'Neyron tarmoqlar', 'ai', '[0.6, 0.2, 0.6]'),
  (8, 'Tranzaksiyalar', 'baza', '[0.85, 0.15, 0.05]'),
  (9, 'Ma''lumotlar bazasi: to''liq kurs', 'baza', '[2.7, 0.6, 0.0]');"""

HIDDEN = """\
CREATE TABLE maqola (
  id INTEGER PRIMARY KEY,
  sarlavha VARCHAR(100) NOT NULL,
  mavzu VARCHAR(30) NOT NULL,
  embedding vector(3) NOT NULL
);
INSERT INTO maqola VALUES
  (1, 'A', 'baza', '[0.1, 0.9, 0.0]'),
  (2, 'B', 'sport', '[0.95, 0.05, 0.0]'),
  (3, 'C', 'baza', '[0.3, 0.3, 0.3]'),
  (4, 'D', 'oshxona', '[0.9, 0.2, 0.1]'),
  (5, 'E', 'ai', '[0.0, 0.0, 1.0]'),
  (6, 'F', 'baza', '[0.5, 0.5, 0.1]'),
  (7, 'G', 'sport', '[0.7, 0.1, 0.2]'),
  (8, 'H', 'baza', '[0.2, 0.1, 0.8]'),
  (9, 'I', 'ai', '[1.8, 0.4, 0.0]');"""

VECTOR_LABS = [
    {
        "title": "Vektorli qidiruv: eng yaqin maqolalar",
        "description": (
            "Foydalanuvchi so'rovining embeddingi: '[0.9, 0.2, 0.0]'. maqola jadvalidan unga Evklid (L2) masofa "
            "bo'yicha eng yaqin 3 ta maqolaning sarlavhasini, eng yaqinidan boshlab chiqaring."
        ),
        "setup_sql": SETUP,
        "solution_sql": "SELECT sarlavha FROM maqola ORDER BY embedding <-> '[0.9, 0.2, 0.0]' LIMIT 3;",
        "hidden_setup_sql": HIDDEN,
        "topic": "vector",
    },
    {
        "title": "Vektorli qidiruv: filtr va kosinus masofa",
        "description": (
            "Faqat «baza» mavzusidagi maqolalar ichidan so'rov vektori '[0.5, 0.0, 0.5]' ga kosinus masofa (<=>) "
            "bo'yicha eng yaqin 2 tasini toping. Natijada sarlavha va masofa (3 xona aniqlikda yaxlitlangan, "
            "ustun nomi masofa) bo'lsin, eng yaqinidan boshlab."
        ),
        "setup_sql": SETUP,
        "solution_sql": (
            "SELECT sarlavha, round((embedding <=> '[0.5, 0.0, 0.5]')::numeric, 3) AS masofa\n"
            "FROM maqola\nWHERE mavzu = 'baza'\nORDER BY embedding <=> '[0.5, 0.0, 0.5]'\nLIMIT 2;"
        ),
        "hidden_setup_sql": HIDDEN,
        "topic": "vector",
    },
]

for _lab in VECTOR_LABS:
    _lab["theory"] = THEORY
