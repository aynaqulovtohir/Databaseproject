# Texnik tekshiruv skriptlari va natijalari

Bu papkada «MB loyihalash» platformasining pilot tadqiqotga tayyorligini tekshirishda ishlatilgan skriptlar va
ularning natijalari bor. Ular maqolaning 3.6, 4.2, 4.4 va 4.5-bo'limlari hamda 2-jadvaliga mos keladi:
«MB loyihalash»: ma'lumotlar bazasini loyihalashni o'qitish uchun jarayonni qayd etuvchi AI platformasini ishlab
chiqish, texnik tekshirish va pilot tadqiqot protokoli (Aynakulov T.T.).

> **Hamma ma'lumot sintetik.** Hisoblar xulqini skript beradi: guruhlar orasida oldindan qo'yilgan farq yo'q, SUS
> javoblari tasodifiy. Statistik qiymatlar faqat hisoblash zanjiri ishlashini ko'rsatadi, o'quv samaradorligi
> yoki foydalanish qulayligi haqida xulosa bermaydi. Skriptlarni **faqat mahalliy ishlab chiqish nusxasida**
> ishga tushiring: ular hisoblar, guruhlar va laboratoriyalar yaratadi.

## Tarkibi

| Fayl | Nima qiladi | Maqolada |
|---|---|---|
| `api.py` | Platforma API'siga so'rov va login (429 bo'lsa kutib qayta urinadi) | — |
| `sintetik.py` | Sintetik talaba: testlarni darajasiga qarab yechadi, ER diagrammani uch xil tartibda (avval obyektlar, aralash, sinab ko'rish) bosqichma-bosqich chizadi va topshiradi | 3.6 |
| `tekshiruv2_tayyorlash.py` | 4 guruh (har bir shartda 2 ta, «tadqiqotga kiradi»), 20 hisob, A/B testlar almashlab, imtihon modulidagi 3 ta ER topshirig'i | 3.6 |
| `tekshiruv2_ishga_tushirish.py` | 20 hisob bir vaqtda kiradi va barcha bosqichlarni bajaradi; login 429 javoblari sanaladi | 4.2, 2-jadval |
| `login_sinovi.py` | Bitta IP'dan 40 ta login so'rovi bir vaqtda | 2-jadval |
| `ai_bloklash_sinovi.py` | Nazorat guruhida AI funksiyalari bloklanishi (AI chaqirilmaydi) | 2-jadval |
| `mashq_tayyorlash.py`, `mashq_ishga_tushirish.py` | Foydalanish sinovi protsedurasining 12 hisobli mashqi | 4.5 |
| `yuklama65_tayyorlash.py`, `yuklama65_ishga_tushirish.py` | 65 sintetik hisob («Sintetik 01…65») bir vaqtda T1–T7: Gemini API limitini sinash | 4.5 |
| `mashq15_tayyorlash.py`, `mashq15_ishga_tushirish.py`, `mashq15_sus_qayta.py` | Xuddi shu mashq 15 hisob bilan (bir mashg'ulotdagi talabalar soni); SUS bosqichini alohida qayta bajarish | 3.7, 4.5 |
| `takroriy_simulyatsiya.py` | Monte Karlo: `backend/competence/stats.py` funksiyalari (ANCOVA, Holm, ICC, t, Mann–Uitni) generator qoidasi bilan yaratilgan 2 000 × 12 ma'lumot to'plamida; soxta ijobiy natijalar ulushi, quvvat va kompetentlik «Umumiy» o'zgarishining eski/tuzatilgan usuli (PR #46). Platforma va bazasiz ishlaydi | sintetik tekshiruv maqolasi, 4.5 va 5.6 |
| `klaster_simulyatsiya.py` | Xuddi shu funksiyalar akademik guruh ta'siri bilan (ICC = 0; 0,05; 0,10): A — AI guruh bo'yicha (har shartda 2 guruh), B — har bir guruh ikkiga bo'linib, yarmi AI, yarmi nazorat; ANCOVA soxta ijobiy ulushi, quvvat va platformaning ICC ogohlantirishi (> 0,05) qanchalik tez-tez ishlashi | sintetik tekshiruv maqolasi, 4.5 va 5.6 |
| `natijalar/` | Loglar va platforma tahlil modullarining chiqishi | — |

## Ishga tushirish tartibi

Mahalliy nusxa ishlab turgan bo'lishi kerak (`sh loyiha.sh`), unda ER laboratoriyalari bo'lishi kerak
(`seed_design_labs`). Konteynerdagi buyruqlar backend konteynerida, `python3` buyruqlari shu papkada bajariladi.

```sh
# 2-texnik tekshiruv
MUALLIF=<o'qituvchi> python manage.py shell < tekshiruv2_tayyorlash.py > tekshiruv2.json
python3 tekshiruv2_ishga_tushirish.py tekshiruv2.json | tee natijalar/tekshiruv2.log
python3 login_sinovi.py tekshiruv2.json | tee natijalar/login_sinovi.txt
python3 ai_bloklash_sinovi.py tekshiruv2.json | tee natijalar/ai_bloklash_sinovi.txt
# Tahlil: platformadagi «Tajriba tahlili» va «ER jarayoni» sahifalari (yoki /api/experiment/, /api/statistics/er-process/)

# Foydalanish sinovi mashqi
MUALLIF=<o'qituvchi> python manage.py shell < mashq_tayyorlash.py > mashq.json
python3 mashq_ishga_tushirish.py mashq.json | tee natijalar/mashq.log
python manage.py usability_report --group FS-MASHQ --learn-lab <id> --exam-lab <id> --sus <id>
python manage.py sus_report --quiz <id> --group FS-MASHQ --consented

# 15 hisobli mashq (2026-11-21)
MUALLIF=<o'qituvchi> python manage.py shell < mashq15_tayyorlash.py > mashq15.json
python3 mashq15_ishga_tushirish.py mashq15.json | tee natijalar/mashq15.log
python3 mashq15_sus_qayta.py mashq15.json | tee natijalar/mashq15_sus_qayta.log   # faqat SUS yopiq bo'lsa
python manage.py usability_report --group FS-MASHQ15 --learn-lab <id> --exam-lab <id> --sus <id>
python manage.py sus_report --quiz <id> --group FS-MASHQ15 --consented

# Takroriy simulyatsiya (2026-11-22): platforma va baza kerak emas, ~1,5 daqiqa; seed qat'iy — natija bir xil chiqadi
python3 -I takroriy_simulyatsiya.py ../../backend/competence/stats.py natijalar/takroriy_simulyatsiya.json
python3 -I klaster_simulyatsiya.py ../../backend/competence/stats.py natijalar/klaster_simulyatsiya.json   # ~4,5 daqiqa
```

`tekshiruv2.json`, `mashq.json` va `mashq15.json` fayllarida sintetik hisoblarning parollari bor, ular repozitoriyaga kiritilmaydi.
Mashqda o'quv laboratoriyasidagi AI (maslahat, murabbiy, AI baholash) haqiqatan chaqiriladi: taxminan 23 ta so'rov.

## Natijalar (2026-yil 3-noyabr)

| Fayl | Asosiy natija |
|---|---|
| `natijalar/tekshiruv2.log` | 20 hisob barcha bosqichlarni bajardi; 60 ta AI'siz ER ishining barchasi avtomatik baholandi, tuzatilgan diagramma ko'rsatilmadi; login 429 — 0 ta |
| `natijalar/tekshiruv2_tahlil.json` | Tahlilga faqat 4 ta belgilangan guruh kirdi; ANCOVA, Hedges g, Holm, TOST, ICC va ER jarayoni (60 ish) hisoblandi |
| `natijalar/login_sinovi.txt` | 40 ta login, hammasi HTTP 200 |
| `natijalar/ai_bloklash_sinovi.txt` | Maslahat, murabbiy, AI buyurtmachi va tushuntirish — HTTP 403; o'qish tavsiyasi AI'siz |
| `natijalar/mashq.log`, `mashq_usability_report.txt`, `mashq_sus_report.txt` | 252 so'rov xatosiz; ataylab o'tkazib yuborilgan 4 topshiriq aniqlandi; bir vaqtdagi so'rovlarda AI baholash 4 marta HTTP 503 qaytarib, avtomatik bahoga o'tdi |

## Natijalar (2026-yil 21-noyabr, 15 hisobli mashq)

| Fayl | Asosiy natija |
|---|---|
| `natijalar/mashq15.log`, `mashq15_usability_report.txt` | 15 hisob bir vaqtda kirdi (HTTP 429 yo'q); 321 so'rov HTTP 200; ataylab o'tkazib yuborilgan 4 topshiriq aniqlandi; AI baholash 6 marta xato qaytardi (4 × HTTP 503, 2 × ulanish xatosi) va avtomatik bahoga o'tdi: o'quv lab baholari 9 AI / 6 AUTO; log to'liqligi (b) 29/30 |
| `natijalar/mashq15_sus_qayta.log`, `mashq15_sus_report.txt` | T7 birinchi ishga tushirishda 15 marta HTTP 400 («Test hozir yopiq»): umumiy SUS so'rovnomasining ochiq vaqti oldingi sinovda tugagan edi (sozlama xatosi). Vaqt vaqtincha ochilib, T7 qayta bajarildi (30 so'rov HTTP 200) va vaqt qaytarildi. Sintetik SUS qiymatlari talqin qilinmaydi |

## Natijalar (2026-yil 21-noyabr, 65 hisobli sintetik yuklama sinovi)

| Fayl | Asosiy natija |
|---|---|
| `natijalar/yuklama65.log`, `yuklama65_usability_report.txt` | 65 hisob 166 soniyada barcha bosqichlarni bajardi (login 429 yo'q, server xatosi yo'q). AIUsage jurnalidagi 128 ta model chaqiruvidan 102 tasi xato bilan tugadi (91 tasi Gemini so'rovlar limiti, 11 tasi HTTP 503): AI baholarning 58/65 tasi avtomatik bahoga o'tdi, maslahat va murabbiy so'rovlarining 44/63 tasi bajarilmadi (talabaga «AI vaqtincha ishlamayapti» ko'rsatildi, HTTP 503). Log to'liqligi (b) 129/130. Xulosa: bir vaqtdagi foydalanuvchilar soni API limiti bilan cheklanadi, mashg'ulotlar bir vaqtda o'tkazilmaydi |

T2 da 2 hisobning mezonga yetmagani (kamida 3 obyekt va 2 bog'lanish) past darajali sintetik hisoblar xulqidan, platforma xatosi emas.

`login_sinovi.txt` va `ai_bloklash_sinovi.txt` shu skriptlar repozitoriyaga qo'shilgach qayta ishga tushirilib
olindi; maqoladagi qiymatlar (40 login, 5,6 s) birinchi ishga tushirishdan, bu fayldagi vaqt farq qilishi mumkin.

## Natijalar (2026-yil 22-noyabr, takroriy simulyatsiya)

`natijalar/takroriy_simulyatsiya.json` (R = 2 000, seed 20261122; har bir shartda n = 10, 20, 64; tajriba guruhiga
δ = 0; 0,05; 0,10; 0,15 qo'shilgan, chiqish testida d = 0; 0,28; 0,53; 0,81):

| Ko'rsatkich | Natija |
|---|---|
| ANCOVA, effekt yo'q (soxta ijobiy) | 5,1% / 4,8% / 4,8% (n = 10 / 20 / 64) — nominal 5% |
| Ikkilamchi 3 taqqoslash, kamida bittasi: tuzatishsiz → Holm | 12,4–13,0% → 4,4–4,7% |
| ANCOVA quvvati, d ≈ 0,53 | 29,6% / 56,5% / 97,9% |
| ICC > 0, klaster ta'siri yo'q | 22–26% takrorda (o'rtacha 0,032 / 0,017 / 0,005) |
| Kompetentlik «Umumiy», haqiqiy o'sishda ahamiyatli «pasayish»: eski usul → tuzatilgan | 56% / 90% / 100% → 0% |

Simulyatsiya statistik funksiyalarni bevosita chaqiradi (API, baza va mezon tanlash qismi chetlab o'tiladi): mezon
har doim Styudent t (chiqish, kechiktirilgan) va Mann–Uitni U (o'sish); klaster ta'siri, tashlab ketish va shift
dasturlanmagan.

## Natijalar (2026-yil 23-noyabr, klaster simulyatsiyasi)

`natijalar/klaster_simulyatsiya.json` (R = 2 000, seed 20261123; 4 ta akademik guruh; guruh ta'siri chiqish testiga
qo'shiladi, σ_u = 3,31 / 4,81 ball ICC = 0,05 / 0,10 ga mos; qoldiq SD = 14,43):

| Dizayn, ICC | ANCOVA soxta ijobiy: n = 10 / 20 / 64 har shartda | Platforma ICC ogohlantirishi (n = 20) |
|---|---|---|
| A (AI guruh bo'yicha), 0 | 5,4% / 5,2% / 5,3% | 11% (soxta signal) |
| A, 0,05 | 8,9% / 11,2% / 24,2% | 24% |
| A, 0,10 | 9,5% / 15,3% / 33,6% | 36% |
| B (guruh ichida bo'lish), 0,05 | 5,0% / 3,7% / 5,3% | — |
| B, 0,10 | 4,4% / 3,9% / 4,2% | — |

Xulosa: AI guruh bo'yicha yoqilsa va har shartda 2 ta guruh bo'lsa, guruh ta'siri soxta ijobiy ulushni guruh hajmi
bilan birga oshiradi; platformaning ICC ogohlantirishi bunday holatlarning ko'pini sezmaydi. Har bir sinfni ikkita
platforma guruhiga bo'lish (B) xatoni nominal darajada saqlaydi, quvvat kamaymaydi (δ = 0,10 da n = 20: 0,56).
B dizaynda sinf ichida AI javoblari almashinishi (kontaminatsiya) xavfi bor.

## Cheklovlar

- **1-texnik tekshiruv** (8 ta hisob, maqolaning 3.5-bo'limi) skripti saqlanmagan, shuning uchun bu papkada yo'q.
  Uning natijalari maqolaning 2-jadvalidagi «1-tekshiruv» ustunida.
- Natijalar platformaning `tadqiqot-tayyorligi` branchidagi holatiga tegishli (PR #40).
- Hisoblar xulqi skriptdan olingani uchun vaqt ko'rsatkichlari (masalan, faol vaqt) real talabalarnikidan farq qiladi.
