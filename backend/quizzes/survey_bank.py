"""Tajriba oxiridagi so'rovnoma: talabalarning virtual laboratoriya va AI maslahatlari haqidagi fikri.

Har bir savol — fikr (tasdiq), talaba unga 1 dan 5 gacha shkalada qo'shiladi yoki qo'shilmaydi.
"ai": True savollar faqat AI yoqilgan (tajriba) guruhlariga beriladi.
"external": True savollar — tashqi AI vositalaridan foydalanish (barcha guruhlarga): ular fikr shkalasiga kirmaydi
(boshqa narsani o'lchaydi), tajriba tahlilida nazorat guruhining "ifloslanishi" ko'rsatkichi sifatida ishlatiladi
(experiment.py). Ular matni bo'yicha topiladi, shuning uchun matnini o'zgartirmang.

Bazaga qo'shish: python manage.py seed_survey --author <login> --group <guruh>
"""

SURVEY_TITLE = "Virtual laboratoriya haqida so'rovnoma"
SURVEY_DESCRIPTION = (
    "Har bir fikrga qanchalik qo'shilishingizni belgilang: 1 — mutlaqo qo'shilmayman, 5 — to'liq qo'shilaman. "
    "To'g'ri yoki noto'g'ri javob yo'q, ball qo'yilmaydi. O'qituvchi alohida javoblaringizni ko'rmaydi, "
    "faqat guruh bo'yicha umumiy natijani ko'radi."
)

STATEMENTS = [
    # Laboratoriya (barcha guruhlar)
    {"ai": False, "text": "Virtual laboratoriyada ishlash menga qulay bo'ldi."},
    {"ai": False, "text": "Laboratoriya topshiriqlari mavzuni tushunishimga yordam berdi."},
    {"ai": False, "text": "Tekshiruv natijasi (xato va namunadan farqlar) nimani tuzatish kerakligini tushunarli ko'rsatdi."},
    {"ai": False, "text": "ER-diagramma chizish ma'lumotlar bazasini loyihalashni tushunishimga yordam berdi."},
    {"ai": False, "text": "Endi ma'lumotlar bazasini mustaqil loyihalashga o'zimni tayyor his qilaman."},
    {"ai": False, "text": "Topshiriqlar qiyinligi men uchun mos edi."},
    # AI maslahatlari (faqat tajriba guruhlari)
    {"ai": True, "text": "AI maslahatlari xatoni topishimga yordam berdi."},
    {"ai": True, "text": "AI maslahatlari tushunarli tilda yozilgan edi."},
    {"ai": True, "text": "Maslahatlar tayyor javobni bermasdan, o'zim o'ylashimga undadi."},
    {"ai": True, "text": "AI maslahatiga tayanib qolmasdan, avval o'zim yechishga harakat qildim."},
    {"ai": True, "text": "AI bergan baho va izohlar adolatli bo'ldi."},
    {"ai": True, "text": "Boshqa fanlarda ham shunday AI yordamchisi bo'lishini xohlardim."},
    # Tashqi AI vositalari (barcha guruhlar; javob bahoga ta'sir qilmaydi)
    {
        "ai": False,
        "external": True,
        "text": "Kurs davomida topshiriqlarni bajarishda platformadan tashqari AI vositalaridan (ChatGPT, Gemini, Copilot va h.k.) foydalandim.",
    },
    {
        "ai": False,
        "external": True,
        "text": "Laboratoriya topshirig'ini yoki test savolini platformadan tashqari AI vositasiga berib, tayyor javob oldim.",
    },
]

EXTERNAL_AI_TEXTS = frozenset(item["text"] for item in STATEMENTS if item.get("external"))
