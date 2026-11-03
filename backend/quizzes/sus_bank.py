"""SUS (System Usability Scale, Brooke, 1996): platformadan foydalanish qulayligi so'rovnomasi.

10 ta fikr qat'iy shu tartibda beriladi: toq raqamlilari ijobiy, juftlari salbiy (hisoblash sus.py da). Lewis (2018)
tavsiyasiga ko'ra "tizim" o'rniga mahsulot nomi ("platforma") ishlatilgan, 8-fikrdagi "cumbersome" esa "noqulay"
deb berilgan. O'zbekcha matn tarjima: rasmiy validatsiyadan o'tgan o'zbekcha SUS yo'q, shuning uchun ishlatishdan
oldin teskari tarjima (back-translation) bilan tekshirish tavsiya etiladi (docs/foydalanish-sinovi.md).

Matnni o'zgartirmang: hisoblash savollarni tartib raqami (Question.order) bo'yicha oladi.

Bazaga qo'shish: python manage.py seed_sus --author <login> --group <guruh>
"""

SUS_TITLE = "Platformadan foydalanish qulayligi (SUS)"
SUS_DESCRIPTION = (
    "«MB loyihalash» platformasida bugun ishlagan tajribangiz haqida. Har bir fikrga qanchalik qo'shilishingizni "
    "belgilang: 1 — mutlaqo qo'shilmayman, 5 — to'liq qo'shilaman. Uzoq o'ylab o'tirmang, birinchi fikringizni "
    "belgilang. Javob berish qiyin bo'lsa, o'rtadagi qiymatni (3) tanlang. Barcha 10 ta fikrga javob bering."
)

# (tartib raqami 1–10, matn). Toq — ijobiy, juft — salbiy fikr.
SUS_ITEMS = [
    "Menimcha, bu platformadan tez-tez foydalanishni xohlardim.",
    "Platforma keragidan ortiq murakkab ekan.",
    "Platformadan foydalanish oson deb o'yladim.",
    "Menimcha, bu platformadan foydalanish uchun texnik mutaxassisning yordami kerak bo'ladi.",
    "Platformadagi turli funksiyalar bir-biri bilan yaxshi uyg'unlashgan.",
    "Platformada nomuvofiqliklar juda ko'p deb o'yladim.",
    "Menimcha, ko'pchilik bu platformadan foydalanishni juda tez o'rganib oladi.",
    "Platformadan foydalanish juda noqulay ekan.",
    "Platformadan foydalanganda o'zimni juda ishonchli his qildim.",
    "Bu platformada ishlashni boshlashdan oldin ko'p narsani o'rganishim kerak bo'ldi.",
]
