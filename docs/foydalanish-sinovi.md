# Foydalanish sinovi (usability study) protokoli

Asosiy pilot tadqiqotdan oldin real talabalar bilan o'tkaziladigan qisqa sinov. U «MB loyihalash» platformasining
texnik tekshiruvi haqidagi maqolaga real foydalanuvchi dalilini qo'shadi va pilotdan oldin interfeys muammolarini
topishga yordam beradi.

**Bu sinov o'quv samaradorligini ham, AI ta'sirini ham o'lchamaydi.** Nazorat guruhi yo'q, natijalar faqat
platformadan foydalanish qulayligi va texnik ishonchliligi haqida.

## 1. Tadqiqot savoli

> Real talabalar platformaning asosiy ish oqimini (kirish, rozilik, ER laboratoriyasi, AI murabbiy, topshirish,
> AI'siz imtihon topshirig'i, so'rovnoma) mustaqil bajara oladimi, ular foydalanish qulayligini qanday baholaydi
> va jarayon loglari real foydalanishda to'liq yoziladimi?

Maqolada bu savol **RQ4** bo'ladi.

## 2. Ishtirokchilar

- **Soni:** 10–15 nafar bakalavr talaba. 5 ta foydalanuvchi interfeys muammolarining katta qismini topadi
  (Nielsen va Landauer, 1993). 10–15 ta foydalanuvchi esa SUS o'rtachasini ishonch oralig'i bilan berishga imkon
  beradi.
- **Kimlar:** ER modellashtirish asoslarini biladigan talabalar. Masalan, «Ma'lumotlar bazasi» fanini o'tgan yuqori
  kurs talabalari yoki boshqa yo'nalish talabalari.
- **Kimlar emas:** keyingi asosiy pilotda qatnashadigan talabalar. Ular platformani oldindan ko'rsa, pilot
  natijasiga aralashadi.
- Ishtirok ixtiyoriy va bahoga ta'sir qilmaydi.

## 3. Platformani tayyorlash (mashg'ulotdan 1–2 kun oldin)

1. **Guruh:** admin «Guruhlar» sahifasida, masalan, `FS-2026` guruhini yaratadi, «AI yordamchisi yoqilgan»
   belgisini qo'yadi.
   - «Tadqiqotga kiradi» belgisini **qo'ymang**. Pilot guruhlari belgilangan bo'lsa ham, bu guruh tadqiqot
     tahlillariga aralashmasligi kerak.
   - Natija pastdagi `sus_report --group` buyrug'i va eksportdagi `guruh` ustuni bilan olinadi.
2. **Hisoblar:** har bir talabaga login va parol yaratiladi va qog'ozda beriladi.
3. **Topshiriqlar:**
   - O'quv ER laboratoriyasi (AI yoqilgan, imtihon rejimisiz), masalan «ER-model 2. Kutubxona».
   - Alohida modulda imtihon rejimidagi bitta qisqa ER topshirig'i, boshqa vaziyat bilan. Imtihon vaqtini
     mashg'ulotning 45–65-daqiqalariga qo'ying.
4. **SUS so'rovnomasi:**
   ```
   python manage.py seed_sus --author <o'qituvchi logini> --group FS-2026
   ```
5. **AI:** Gemini API kaliti ishlashini va kunlik limitlar 15 talabaga yetishini tekshiring.
6. **Sinab ko'rish:** bitta sinov hisobi bilan butun ssenariyni boshidan oxirigacha o'tib chiqing.
7. **Auditoriya:** kompyuterlar, brauzer va internetni tekshiring. Hamma bitta IP manzildan kirsa ham login
   cheklovi endi xalaqit bermaydi.

## 4. SUS tarjimasini tekshirish (mashg'ulotdan oldin)

Rasmiy tasdiqlangan o'zbekcha SUS yo'q. Matn `backend/quizzes/sus_bank.py` faylida.

1. **Teskari tarjima:** ingliz tilini biladigan, platformani bilmaydigan ikki kishi o'zbekcha matnni mustaqil
   ravishda inglizchaga qaytaradi. Asl matndan farqlar muhokama qilinib, kelishiladi.
2. **Kognitiv intervyu:** sinovda qatnashmaydigan 2–3 talaba har bir fikrni o'z so'zi bilan tushuntiradi.
   Noaniq so'zlar tuzatiladi.
3. **Hujjatlash:** o'zgartirishlar va ularning sababi yozib qo'yiladi. Ular maqolaning metod qismiga kiradi.

> Matn o'zgarsa, `sus_bank.py` ni so'rovnoma yaratilishidan **oldin** yangilang. Hisoblash savollar tartibiga
> tayanadi, shuning uchun 10 ta fikrning tartibi (toq — ijobiy, juft — salbiy) o'zgarmasligi kerak.

## 5. Mashg'ulot ssenariysi (80 daqiqa)

| Vaqt | Bosqich | Kuzatuvchi nima qiladi |
|---|---|---|
| 0–10 | Tanishtirish, qog'oz rozilik varaqasi (8-bo'lim) | Maqsadni tushuntiradi: «Platformani sinayapmiz, sizni emas» |
| 10–15 | **T1.** Platformaga kirish va rozilik qarorini berish | Yordam bermaydi, vaqtni yozadi |
| 15–45 | **T2–T5.** O'quv ER laboratoriyasi (AI bilan) | 3 daqiqadan ortiq tiqilib qolgan talabaga yordam beradi va buni yozib qo'yadi |
| 45–65 | **T6.** Imtihon rejimidagi ER topshirig'i (AI'siz) | Yordam bermaydi |
| 65–75 | **T7.** SUS so'rovnomasi va 3 ta ochiq savol | «Barcha 10 ta fikrga javob bering» deb eslatadi |
| 75–80 | Yakun, minnatdorchilik | — |

### Topshiriqlar va muvaffaqiyat mezoni

| № | Topshiriq | Muvaffaqiyatli deb hisoblanadi, agar… |
|---|---|---|
| T1 | Platformaga kirish va rozilik qarorini berish | bosh sahifaga yordamisiz chiqsa |
| T2 | ER laboratoriyasini ochish, kamida 3 obyekt va 2 bog'lanish chizish | diagrammada shular bo'lsa |
| T3 | «Tekshirish» tugmasidan foydalanib, xato ro'yxatini tushunish | kamida bitta xatoni ro'yxat asosida tuzatsa |
| T4 | Darajali maslahat yoki AI murabbiydan foydalanish | kamida bitta murojaat bo'lsa |
| T5 | Diagrammani baholashga topshirish | ball olsa |
| T6 | Imtihon topshirig'ini AI'siz bajarib topshirish | belgilangan vaqtda topshirsa |
| T7 | SUS so'rovnomasini to'liq to'ldirish | 10 ta fikrning hammasiga javob bersa |

**Ogohlantirish:** platforma so'rovnomani to'liq to'ldirilmagan holda ham qabul qiladi. Shuning uchun T7 da
eslatma muhim. To'liqsiz javoblar SUS hisobidan chiqariladi va alohida sanaladi.

### Ochiq savollar

Platformada matnli javob turi yo'q, shuning uchun bu savollar qog'ozda yoki onlayn shaklda beriladi:

1. Platformada sizga eng ko'p nima yoqdi?
2. Qaysi joyda eng ko'p qiynaldingiz yoki adashdingiz?
3. Bitta narsani o'zgartirish imkoningiz bo'lsa, nimani o'zgartirardingiz?

## 6. O'lchovlar

| O'lchov | Manba | Qanday olinadi |
|---|---|---|
| **SUS bali (asosiy)** | Platformadagi SUS so'rovnomasi | `python manage.py sus_report --quiz <id> --group FS-2026 --consented` |
| Topshiriq bajarilishi | Kuzatuv varag'i (9-bo'lim) | Har bir T uchun: 2 — mustaqil, 1 — yordam bilan, 0 — bajarmadi; vaqti |
| Interfeys muammolari | Kuzatuv varag'i va ochiq javoblar | Tavsif, qaysi T, nechta talabada; og'irligi Nielsen shkalasida (0–4) |
| Log to'liqligi | Tadqiqot eksporti (`er_jarayon` fayllari) | Kamida 5 oraliq holati bor va jarayoni tiklangan ER ishlari ulushi |
| AI ishlatilishi | Tadqiqot eksporti (`ai_foydalanish.csv`) | Talaba boshiga murojaatlar soni va turi |
| Server xatolari | `sh loyiha.sh log` (yoki server logi) | Mashg'ulot vaqtidagi HTTP 5xx soni |

## 7. Tahlil va oldindan belgilangan mezonlar

**Tahlil:**
- **SUS:** o'rtacha, SD, mediana, 95% CI, 68 lik me'yor bilan solishtirish, Sauro–Lewis bahosi va Cronbach α. Bularning hammasini `sus_report` chiqaradi.
- **Topshiriqlar:** mustaqil bajarilish ulushi va 95% CI (Wilson usuli).
- **Muammolar:** og'irlik darajasi bo'yicha ro'yxat.
- **Ochiq javoblar:** qisqa tematik kodlash.

**Mezonlar (sinovdan oldin qayd eting, keyin o'zgartirmang):**

| Mezon | Chegara |
|---|---|
| SUS o'rtachasi | ≥ 68 |
| T1–T7 ni mustaqil bajarish | ≥ 80% |
| Log to'liqligi | ≥ 90% (pilotdagi davom ettirish mezoni bilan bir xil) |
| 4-darajali (halokatli) muammo | yo'q |

Mezon bajarilmasa, muammo tuzatiladi va pilotdan oldin qisqa qayta sinov o'tkaziladi. Bu holat maqolada ochiq
yoziladi.

## 8. Etika va rozilik

- Universitet etika qo'mitasi talabini oldindan aniqlang. Ruxsat kerak bo'lsa, shu protokolni ilova qiling.
- Platformadagi elektron rozilik loglar va so'rovnomaga tegishli. Kuzatuv uchun qo'shimcha qog'oz rozilik olinadi.

### Rozilik varaqasi (namuna)

> **Platformadan foydalanish qulayligini sinashda ishtirok etishga rozilik**
>
> Siz «MB loyihalash» o'quv platformasining qulayligini sinashga taklif qilinyapsiz. Mashg'ulot taxminan 80 daqiqa
> davom etadi. Siz ER diagramma topshiriqlarini bajarasiz va qisqa so'rovnomani to'ldirasiz. Tadqiqotchi ishingizni
> kuzatib, qayerda qiynalganingizni yozib boradi. **Bilimingiz baholanmaydi va fan bo'yicha bahoyingizga hech qanday
> ta'sir qilmaydi.**
>
> Platforma laboratoriyadagi harakatlaringizni (diagramma o'zgarishlari, tekshiruvlar, AI murojaatlari) va so'rovnoma
> javoblaringizni yozib oladi. Tahlilda ismingiz va loginingiz ishlatilmaydi, siz taxallus bilan ko'rsatilasiz.
> Natijalar faqat umumlashgan holda ilmiy maqolada e'lon qilinadi.
>
> Ishtirok ixtiyoriy. Istalgan paytda sabab ko'rsatmasdan to'xtatishingiz mumkin.
>
> Savollar uchun: [tadqiqotchi ismi, e-pochta]
>
> Ism-familiya: __________________  Imzo: __________  Sana: __________

## 9. Kuzatuv varag'i (har bir talaba uchun)

| Taxallus | T1 | T2 | T3 | T4 | T5 | T6 | T7 | Izoh (qayerda tiqildi, nima dedi) |
|---|---|---|---|---|---|---|---|---|
| FS-01 | 2 / 3′ | | | | | | | |

Har bir katakka bajarilish (2/1/0) va vaqtni yozing (masalan, `2 / 3′`).

**Muammolar ro'yxati:**

| № | Muammo | Topshiriq | Nechta talabada | Og'irligi (0–4) |
|---|---|---|---|---|
| 1 | | | | |

Og'irlik (Nielsen): 0 — muammo emas, 1 — kosmetik, 2 — kichik, 3 — katta, 4 — halokatli (topshiriqni bajarib
bo'lmaydi).

## 10. Maqolaga qanday kiradi

- **Metodlar:** «3.7. Foydalanish sinovi» bo'limi. Unda ishtirokchilar, ssenariy, SUS tarjimasi va mezonlar
  yoritiladi.
- **Natijalar:** «4.5. Foydalanish sinovi (RQ4)». SUS (M, SD, 95% CI, baho), topshiriqlar jadvali, muammolar
  ro'yxati va log to'liqligi beriladi.
- **Cheklovlar:** kichik tanlanma, bitta muassasa, SUS tarjimasi rasmiy validatsiyadan o'tmagan, kuzatuvchi
  platforma muallifi.

### Qo'shimcha manbalar

DOI'larni Crossref orqali tekshiring.

- Bangor, A., Kortum, P. T., & Miller, J. T. (2008). An empirical evaluation of the System Usability Scale.
  *International Journal of Human–Computer Interaction, 24*(6), 574–594. https://doi.org/10.1080/10447310802205776
- Brooke, J. (1996). SUS: A "quick and dirty" usability scale. In P. W. Jordan, B. Thomas, B. A. Weerdmeester, &
  I. L. McClelland (Eds.), *Usability evaluation in industry* (pp. 189–194). Taylor & Francis.
- Lewis, J. R. (2018). The System Usability Scale: Past, present, and future. *International Journal of
  Human–Computer Interaction, 34*(7), 577–590. https://doi.org/10.1080/10447318.2018.1455307
- Nielsen, J., & Landauer, T. K. (1993). A mathematical model of the finding of usability problems. In
  *Proceedings of the INTERACT '93 and CHI '93 Conference on Human Factors in Computing Systems* (pp. 206–213).
  https://doi.org/10.1145/169059.169166
- Sauro, J., & Lewis, J. R. (2016). *Quantifying the user experience: Practical statistics for user research*
  (2nd ed.). Morgan Kaufmann.
