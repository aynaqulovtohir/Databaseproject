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
```

`tekshiruv2.json` va `mashq.json` fayllarida sintetik hisoblarning parollari bor, ular repozitoriyaga kiritilmaydi.
Mashqda o'quv laboratoriyasidagi AI (maslahat, murabbiy, AI baholash) haqiqatan chaqiriladi: taxminan 23 ta so'rov.

## Natijalar (2026-yil 3-noyabr)

| Fayl | Asosiy natija |
|---|---|
| `natijalar/tekshiruv2.log` | 20 hisob barcha bosqichlarni bajardi; 60 ta AI'siz ER ishining barchasi avtomatik baholandi, tuzatilgan diagramma ko'rsatilmadi; login 429 — 0 ta |
| `natijalar/tekshiruv2_tahlil.json` | Tahlilga faqat 4 ta belgilangan guruh kirdi; ANCOVA, Hedges g, Holm, TOST, ICC va ER jarayoni (60 ish) hisoblandi |
| `natijalar/login_sinovi.txt` | 40 ta login, hammasi HTTP 200 |
| `natijalar/ai_bloklash_sinovi.txt` | Maslahat, murabbiy, AI buyurtmachi va tushuntirish — HTTP 403; o'qish tavsiyasi AI'siz |
| `natijalar/mashq.log`, `mashq_usability_report.txt`, `mashq_sus_report.txt` | 252 so'rov xatosiz; ataylab o'tkazib yuborilgan 4 topshiriq aniqlandi; bir vaqtdagi so'rovlarda AI baholash 4 marta HTTP 503 qaytarib, avtomatik bahoga o'tdi |

`login_sinovi.txt` va `ai_bloklash_sinovi.txt` shu skriptlar repozitoriyaga qo'shilgach qayta ishga tushirilib
olindi; maqoladagi qiymatlar (40 login, 5,6 s) birinchi ishga tushirishdan, bu fayldagi vaqt farq qilishi mumkin.

## Cheklovlar

- **1-texnik tekshiruv** (8 ta hisob, maqolaning 3.5-bo'limi) skripti saqlanmagan, shuning uchun bu papkada yo'q.
  Uning natijalari maqolaning 2-jadvalidagi «1-tekshiruv» ustunida.
- Natijalar platformaning `tadqiqot-tayyorligi` branchidagi holatiga tegishli (PR #40).
- Hisoblar xulqi skriptdan olingani uchun vaqt ko'rsatkichlari (masalan, faol vaqt) real talabalarnikidan farq qiladi.
