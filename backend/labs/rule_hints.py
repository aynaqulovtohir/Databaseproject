"""Nazorat guruhi uchun xato turi bo'yicha tayyor tushuntirish (AI'siz).

Tajriba guruhida xato urinishdan keyin talaba AI maslahatini so'raydi. Nazorat guruhida AI o'chirilgan, lekin talaba
ham xuddi shunday tugma bilan yordam so'ray olishi kerak — aks holda guruhlar faqat AI bilan emas, olgan teskari
aloqa hajmi bilan ham farq qiladi. Shu sababli nazorat guruhiga tekshiruv natijasidagi har bir farq turiga oldindan
yozilgan tushuntirish beriladi. Tushuntirish tushuncha yoki qoidani nomlaydi, lekin to'g'ri javobni aytmaydi
(AI maslahatining 2-darajasiga yaqin). Farq turi tekshiruvchilar (er.py, norm.py, checker.py, probes.py) yozadigan
matn andozasidan aniqlanadi; SQL xatolari uchun checker.ERROR_TIPS ishlatiladi.
"""
import re

from .mistakes import mistakes_of

MAX_HINTS = 4

# (andoza, tushuntirish). Tartib muhim: birinchi mos kelgan andoza olinadi.
RULES = [
    # --- ER-diagramma (er.py)
    (r"Diagramma bo.sh",
     "Avval shartdagi obyektlarni chizing, so'ng ularning atributlari va bog'lanishlarini qo'shing."),
    (r"ta obyekt yetishmaydi",
     "Shartdagi tushuncha alohida obyekt bo'ladi, agar uning o'z xususiyatlari bo'lsa yoki u bir nechta boshqa "
     "tushuncha bilan bog'lansa. Shartni qayta o'qib, sanalgan har bir tushuncha diagrammada bormi, tekshiring."),
    (r"^Ortiqcha obyekt",
     "Diagrammaga faqat shartda talab qilingan tushunchalar kiradi. Ortiqcha obyekt shartdagi qaysi jumlaga "
     "tayanishini aniqlang: tayanmasa, u kerak emas yoki boshqa obyektning atributi."),
    (r"ta atribut yetishmaydi",
     "Obyekt atributlari — shartda shu obyekt uchun sanalgan xususiyatlar. Shartdagi ro'yxatni diagrammadagi "
     "atributlar bilan bittalab solishtiring."),
    (r"ortiqcha atribut",
     "Atribut aynan shu obyektning xususiyati bo'lishi kerak. Boshqa obyektga tegishli ma'lumot atribut sifatida "
     "takrorlanmaydi: u bog'lanish orqali ifodalanadi."),
    (r"asosiy kalit \(PK\) belgilanmagan",
     "Har bir obyektning o'z nusxalarini yagona aniqlaydigan asosiy kaliti bo'lishi kerak. Qaysi atribut ikki "
     "nusxada hech qachon takrorlanmasligini aniqlang."),
    (r"asosiy kaliti \(PK\) noto.g.ri",
     "Asosiy kalit takrorlanmaydigan va o'zgarmaydigan atribut bo'lishi kerak. Tanlangan atribut ikki xil nusxada "
     "bir xil bo'lishi mumkinmi? Shartda kalit haqida nima deyilgan?"),
    (r"oraliq obyekti orqali",
     "Ko'p-ko'p bog'lanish konseptual modelda ikki obyekt orasida to'g'ridan-to'g'ri chiziladi; oraliq jadval "
     "keyinroq — relyatsion sxemaga o'tishda paydo bo'ladi."),
    (r"kardinalligi noto.g.ri",
     "Kardinallik har bir tomon uchun alohida aniqlanadi: «bitta A nechta B bilan bog'lanadi?» va «bitta B nechta "
     "A bilan bog'lanadi?». Javobni shartdagi biznes qoidasidan toping: «bir nechta», «ko'p» — N, «aynan bitta», "
     "«faqat bitta» — 1."),
    (r"orasida bog.lanish yetishmaydi",
     "Ikki obyekt orasidagi har bir biznes qoidasi alohida bog'lanishdir; bir xil obyektlar jufti orasida bir "
     "nechta bog'lanish bo'lishi mumkin. Shartdagi qoidalarni bog'lanishlar bilan bittalab solishtiring."),
    (r"orasida ortiqcha bog.lanish",
     "Har bir bog'lanish shartdagi biznes qoidasiga tayanishi kerak. Ikki obyekt boshqa obyekt orqali allaqachon "
     "bog'langan bo'lsa, ular orasidagi to'g'ridan-to'g'ri bog'lanish ortiqcha bo'lishi mumkin."),
    # --- Normallashtirish (norm.py)
    (r"kalit emas: uning yopilmasi",
     "Atributlar to'plami kalit bo'lishi uchun uning yopilmasi (funksional bog'liqliklar orqali aniqlanadigan "
     "barcha atributlar) jadvaldagi hamma atributlarni qamrashi kerak. Yopilmani qadam-baqadam hisoblang."),
    (r"superkalit, lekin minimal emas",
     "Nomzod kalit minimal bo'lishi kerak: undan birorta atributni olib tashlasangiz, u kalit bo'lmay qoladi. "
     "Har bir atributni olib tashlab, yopilmani qayta tekshiring."),
    (r"Barcha nomzod kalitlar topilmadi",
     "Jadvalda bir nechta nomzod kalit bo'lishi mumkin. Hech bir bog'liqlikning o'ng tomonida uchramaydigan "
     "atributlar har bir kalitga albatta kiradi — izlashni shulardan boshlang."),
    (r"Hozirgi normal forma noto.g.ri",
     "Normal formani bosqichma-bosqich tekshiring: 2NF — kalitning bir qismiga bog'liq atribut yo'q; 3NF — kalit "
     "bo'lmagan atributga bog'liq kalit bo'lmagan atribut yo'q; BCNF — har bir bog'liqlikning chap tomoni "
     "superkalit."),
    (r"Dekompozitsiya barcha atributlarni qamramaydi",
     "Dekompozitsiyadagi jadvallar birgalikda asl jadvalning barcha atributlarini o'z ichiga olishi kerak."),
    (r"Dekompozitsiya yo.qotishli",
     "Ajratishni har doim yangi jadval kaliti bo'yicha bajaring: shunda jadvallarni bog'lovchi umumiy atribut "
     "ulardan birida kalit bo'ladi va birlashtirganda soxta qatorlar paydo bo'lmaydi."),
    (r"^R\d+\{.*\} (?:2NF|3NF|BCNF) da emas",
     "Ajratilgan har bir jadvalda bog'liqlikning chap tomoni shu jadvalning kaliti bo'lishi kerak. Buzilgan "
     "bog'liqlikni alohida jadvalga ajrating: uning chap tomoni yangi jadvalning kaliti bo'ladi."),
    # --- SQL tuzilmasi (checker.py)
    (r"jadvali yo.q",
     "Shartda talab qilingan barcha jadvallar yaratilishi kerak; jadval nomlari shartdagidek yozilganini tekshiring."),
    (r"^Ortiqcha jadval",
     "Faqat shartda talab qilingan jadvallarni yarating."),
    (r"ustun yetishmaydi|ortiqcha ustun",
     "Jadval ustunlari shartdagi ro'yxat bilan aynan mos bo'lishi kerak: nomi ham, soni ham."),
    (r"ustunining turi",
     "Ustun turi shartda ko'rsatilgan turga mos bo'lishi kerak."),
    (r"NOT NULL bo.lishi kerak",
     "«Majburiy», «albatta ko'rsatiladi» kabi qoidalar NOT NULL cheklovi bilan ta'minlanadi."),
    (r"bo.sh \(NULL\) qiymatga ruxsat",
     "«Noma'lum bo'lishi mumkin», «ixtiyoriy» degan qoida ustun NULL qiymatni qabul qilishini bildiradi."),
    (r"cheklovi yetishmaydi",
     "Har bir biznes qoidasini cheklov turiga moslang: yagona aniqlash — PRIMARY KEY, takrorlanmaslik — UNIQUE, "
     "boshqa jadvalga ishora — FOREIGN KEY, qiymat chegarasi — CHECK. Shartdagi qoidalarni cheklovlar bilan "
     "bittalab solishtiring."),
    (r"qiymatlar kutilganidan farq|ma.lumotlar kutilganidan farq|natija kutilganidan farq",
     "Natijani shart bilan solishtiring: qaysi qator ortiqcha yoki yetishmayapti, filtr va tartiblash shartlari "
     "to'g'rimi."),
    # --- Sinovlar (probes.py)
    (r"o.tib ketdi",
     "Bu noto'g'ri ma'lumot rad etilishi kerak edi: uni qaysi biznes qoidasi taqiqlaydi va bu qoida qaysi cheklov "
     "bilan ta'minlanadi?"),
    (r"rad etildi, lekin u to.g.ri",
     "Cheklov haddan tashqari qattiq: u to'g'ri ma'lumotni ham rad etyapti. Chegaraviy qiymatlarni (0, NULL, eng "
     "kichik ruxsat etilgan qiymat) qayta ko'rib chiqing."),
    (r"Yashirin sinovlar",
     "Cheklov faqat ko'rinadigan misollarga emas, qoidaning o'ziga mos bo'lishi kerak: qoidani umumiy holda ifodalang."),
]
_COMPILED = [(re.compile(pattern), text) for pattern, text in RULES]

GENERAL = (
    "Tekshiruv natijasidagi farqni shart bilan solishtiring: qaysi talab bajarilmagan va u qaysi tushunchaga "
    "(obyekt, kalit, bog'lanish, normal forma yoki cheklov) tegishli ekanini aniqlang."
)


def explanation_for(text):
    for pattern, explanation in _COMPILED:
        if pattern.search(text):
            return explanation
    return None


def rule_hints(attempt):
    """Xato urinish uchun tayyor tushuntirishlar: [{"problem", "explanation"}], takrorsiz, ko'pi bilan MAX_HINTS ta."""
    hints, seen = [], set()
    for _key, kind, text, tip in mistakes_of(attempt.feedback):
        explanation = tip if kind == "error" and tip else explanation_for(text)
        if not explanation or explanation in seen:
            continue
        seen.add(explanation)
        hints.append({"problem": text, "explanation": explanation})
        if len(hints) >= MAX_HINTS:
            break
    if not hints:
        hints.append({"problem": "", "explanation": GENERAL})
    return hints
