"""Normallashtirish bo'yicha tayyor laboratoriyalar (labs/norm.py tekshiradi)."""
from .norm import parse_task

THEORY = """\
Funksional bog'liqlik (FB) X -> Y: X qiymatlari bir xil bo'lgan ikki qatorda Y ham bir xil.

Atributlar yopilmasi X+ — X dan kelib chiqadigan barcha atributlar. Hisoblash: X dan boshlab, chap tomoni to'plamda
bor har bir FB ning o'ng tomonini qo'shib boring, to'plam o'zgarmay qolguncha.

Nomzod kalit — yopilmasi barcha atributlar bo'lgan MINIMAL to'plam (biror atributini olib tashlasangiz, kalit
bo'lmay qoladi). Kalitlar bir nechta bo'lishi mumkin. Biror kalitga kiradigan atribut — asosiy (prime) atribut.

Normal formalar:
- 2NF: asosiy bo'lmagan atribut kalitning QISMIga bog'liq emas (qisman bog'liqlik yo'q);
- 3NF: har bir X -> A uchun X superkalit yoki A asosiy atribut (tranzitiv bog'liqlik yo'q);
- BCNF: har bir X -> A uchun X superkalit.

Dekompozitsiya talablari: barcha atributlar qamralgan; yo'qotishsiz birlashish (jadvallarni JOIN qilganda soxta
qatorlar paydo bo'lmaydi — umumiy atributlar biror jadvalda kalit); 3NF da har bir FB biror jadval ichida
tekshirilishi mumkin (bog'liqliklar saqlanadi).

Namuna (boshqa mavzu): R(a, b, c), a -> b, b -> c.
```
{a}+ = {a, b, c}  =>  kalit: {a}
b -> c: b kalit emas va c asosiy emas  =>  tranzitiv bog'liqlik, 2NF
3NF: R1(a, b), R2(b, c) — umumiy atribut b, u R2 da kalit: yo'qotishsiz
```"""

NORM_LABS = [
    {
        "kind": "norm",
        "title": "Normallashtirish: talabalar baholari",
        "description": (
            "Dekanat bitta jadvalda talaba, fan va bahoni saqlaydi. Talabaning ismi uning raqamiga, fanning nomi va "
            "kafedrasi fan raqamiga bog'liq; baho esa talaba va fan juftligiga. Nomzod kalitlarni, jadvalning hozirgi "
            "normal formasini toping va uni 3NF ga keltiring."
        ),
        "norm_task": parse_task(
            "talaba_id, ism, fan_id, fan_nomi, kafedra, baho",
            "talaba_id -> ism\nfan_id -> fan_nomi, kafedra\ntalaba_id, fan_id -> baho",
            "3NF",
        ),
    },
    {
        "kind": "norm",
        "title": "Normallashtirish: buyurtmalar va tranzitiv bog'liqlik",
        "description": (
            "Onlayn do'kon buyurtmalar jadvali: har bir buyurtmaning bitta mijozi bor, mijozning shahri, shaharning "
            "esa yetkazish narxi aniq. Kalitni, normal formani toping va jadvalni 3NF ga keltiring."
        ),
        "norm_task": parse_task(
            "buyurtma_id, sana, mijoz_id, mijoz_ismi, shahar, yetkazish_narxi",
            "buyurtma_id -> sana, mijoz_id\nmijoz_id -> mijoz_ismi, shahar\nshahar -> yetkazish_narxi",
            "3NF",
        ),
    },
    {
        "kind": "norm",
        "title": "Normallashtirish: BCNF va bir nechta kalit",
        "description": (
            "Dars jadvali: har bir talaba har bir fanni bitta o'qituvchidan o'qiydi; har bir o'qituvchi faqat bitta "
            "fanni o'qitadi (lekin bitta fanni bir nechta o'qituvchi o'qitishi mumkin). Barcha nomzod kalitlarni va "
            "normal formani toping, jadvalni BCNF ga keltiring. 3NF dan farqi nimada?"
        ),
        "norm_task": parse_task("talaba, fan, oqituvchi", "talaba, fan -> oqituvchi\noqituvchi -> fan", "BCNF"),
    },
]

for _lab in NORM_LABS:
    _lab["theory"] = THEORY
