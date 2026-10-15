# Platforma ma'lumotlar bazasining ER-diagrammasi

Diagrammalar Django modellaridan avtomatik hosil qilinadi, shuning uchun har doim haqiqiy sxemaga mos keladi.

| Fayl | Mazmuni | Qayerda ishlatish |
|---|---|---|
| `konseptual.png` / `.svg` | Obyektlar va ular orasidagi bog'lanishlar (Chen yozuvi, o'zbekcha nomlar, kardinallik) | Dissertatsiya matni (3-bob) |
| `fizik.png` / `.svg` | Barcha jadvallar: ustunlar, turlar, PK/FK/UQ, Crow's Foot bog'lanishlar | Ilova |
| `*.dot` | Graphviz manba fayllari | Qayta chizish uchun |

Word hujjatiga PNG ni qo'ying. SVG sifatini yo'qotmasdan kattalashadi (LibreOffice va Word 365 qo'llaydi).

## Belgilar

- **PK**: asosiy kalit; **FK**: tashqi kalit; **UQ**: takrorlanmas qiymat (UNIQUE); **(null)**: bo'sh bo'lishi mumkin.
- Fizik modelda: `‖` — aniq bitta, `○‖` — nol yoki bitta, `○<` — nol yoki ko'p.
- Konseptual modelda: to'rtburchak — obyekt (entity), romb — bog'lanish, chiziq yonidagi `1`, `N`, `M`, `0..1` — kardinallik.

## Jadvallar

15 ta asosiy jadval va 4 ta oraliq jadval (ko'p-ko'p bog'lanishlar uchun), jami 19 ta. Django'ning ichki ruxsat jadvallari (`auth_*`) mavzuga kirmagani uchun ko'rsatilmagan.

| Modul | Jadval | Vazifasi |
|---|---|---|
| Foydalanuvchilar | `users_user` | Admin, o'qituvchi va talaba (rol ustuni bilan); talaba bitta guruhga tegishli |
| | `users_studentgroup` | Talabalar guruhi |
| | `users_studentgroup_teachers` | Oraliq jadval: guruh ↔ o'qituvchi (M:N) |
| O'quv jarayoni | `learning_material` | O'quv materiali (matn) |
| | `learning_materialfile` | Materialga biriktirilgan fayllar (1:N) |
| | `learning_assignment` | Topshiriq: shart, baholash mezonlari, muddat |
| | `learning_material_groups`, `learning_assignment_groups` | Oraliq jadvallar: material/topshiriq ↔ guruh (M:N) |
| Yechimlar | `submissions_submission` | Talabaning SQL yechimi; (topshiriq, talaba, urinish raqami) takrorlanmaydi |
| | `ai_aianalysis` | Yechimning AI tahlili (1:1): xulosa, muammolar, taklif qilingan ball |
| | `grading_grade` | O'qituvchi qo'ygan baho (1:1) |
| | `ai_chatmessage` | Talabaning topshiriq bo'yicha AI bilan suhbati |
| Bildirishnomalar | `notifications_notification` | Telegram orqali yuboriladigan xabarlar navbati |
| | `notifications_telegramaccount` | Foydalanuvchining Telegram hisobi (1:1) |
| | `notifications_telegramlinkcode` | Telegram bog'lash uchun vaqtinchalik kod (1:1, xeshlangan) |
| Virtual laboratoriya | `labs_lab` | Laboratoriya: shart, tayyor jadvallar, namunaviy yechim |
| | `labs_lab_groups` | Oraliq jadval: laboratoriya ↔ guruh (M:N) |
| | `labs_labattempt` | Talabaning har bir ishga tushirishi va tekshiruv natijasi |
| | `labs_labgrade` | Talabaning laboratoriya bo'yicha eng yuqori bahosi; (laboratoriya, talaba) takrorlanmaydi |

## Loyihalash qarorlari (dissertatsiya uchun)

- **Normallashtirish.** Jadvallar 3NF da: har bir atribut faqat o'z jadvalining kalitiga bog'liq. Masalan, guruh nomi talaba jadvalida takrorlanmaydi, `group_id` orqali olinadi.
- **Ko'p-ko'p bog'lanishlar** (guruh ↔ o'qituvchi, topshiriq ↔ guruh va boshqalar) oraliq jadvallar orqali amalga oshirilgan.
- **Biri-biriga (1:1) bog'lanishlar** (yechim ↔ AI tahlili, yechim ↔ baho) alohida jadvalda saqlanadi: ular keyinroq va boshqa jarayonda paydo bo'ladi, yechim jadvalini esa bo'sh ustunlar bilan to'ldirmaydi.
- **Ma'lumot yaxlitligi** bazaning o'zida cheklovlar bilan ta'minlanadi: UNIQUE (masalan, bitta talabaga bitta laboratoriya bahosi) va o'chirish qoidalari. Materiali, topshirig'i yoki laboratoriyasi bor o'qituvchini o'chirib bo'lmaydi (PROTECT): u faqat bloklanadi. Talaba o'chirilsa, uning yechimlari va urinishlari ham o'chadi (CASCADE).
- **Denormallashtirishning ongli holati:** `labs_labattempt.feedback` (jsonb) tekshiruv natijasini o'zgarmas tarixiy yozuv sifatida saqlaydi.

## Qayta hosil qilish

Baza tuzilishi o'zgarsa (loyiha ildizidan):

```sh
podman compose exec -T backend python manage.py shell < docs/er-diagramma/yaratish.py
mv backend/er-diagramma-fizik.dot docs/er-diagramma/fizik.dot
mv backend/er-diagramma-konseptual.dot docs/er-diagramma/konseptual.dot
cd docs/er-diagramma
for n in fizik konseptual; do dot -Tsvg $n.dot -o $n.svg; dot -Tpng -Gdpi=150 $n.dot -o $n.png; done
```
