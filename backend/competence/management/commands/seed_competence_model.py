"""Dissertatsiyadagi kompetentlik modelini yaratadi: 4 komponent, ularning ko'rsatkichlari va 4 daraja.

Ishga tushirish:
    python manage.py seed_competence_model [--replace]

Bu — boshlang'ich namuna: komponentlar, ko'rsatkichlar, vaznlar va daraja chegaralari admin panelda
ilmiy rahbar bilan kelishilgan metodikaga moslanadi. Testlar turiga qarab avtomatik bog'lanadi: kirish testlari —
tajriba boshiga, chiqish testlari va so'rovnomalar — tajriba oxiriga, kechiktirilgan testlar — tajribadan keyingi
kesimga. Model bor bo'lsa, --replace bilan qayta yaratiladi (eski komponentlar o'chiriladi).
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quizzes.models import Quiz

from ...models import Component, Indicator

S = Indicator.Source
DESIGN_TOPICS = ["er", "design", "norm", "er_sql"]

# Dissertatsiyadagi model (1.1-paragraf, 2.1-paragrafning 2.3-jadvali): to'rt komponent va to'rt daraja.
# Motivatsion va ijtimoiy (kommunikativ) komponentlar muallif qarori bilan modelga kiritilmagan.
# Laboratoriya ko'rsatkichlari loyihalash mavzulari (DESIGN_TOPICS) bilan cheklangan: model ma'lumotlar bazasini
# LOYIHALASH kompetentligini o'lchaydi (SELECT, indeks, tranzaksiya va h.k. kursning boshqa qismi).
# Vaznlar: loyihalash laboratoriyalari amaliy-loyihaviy komponentning asosiy ko'rsatkichi (2), qolganlari 1;
# ular ekspert baholash natijasida admin panelda aniqlashtiriladi.
LEVELS = {"medium_from": 40, "high_from": 70, "creative_from": 85}

MODEL = [
    {
        "name": "Kognitiv",
        "description": "ER-model, relyatsion model, kalitlar, bog'lanishlar, normallashtirish, cheklovlar va SQL bo'yicha bilimlar.",
        "indicators": [
            {
                "name": "Kirish, chiqish va kechiktirilgan test natijasi",
                "source": S.QUIZ,
                "initial": [Quiz.Kind.PRE],
                "final": [Quiz.Kind.POST],
                "delayed": [Quiz.Kind.DELAYED],
            },
        ],
    },
    {
        "name": "Amaliy-loyihaviy",
        "description": "Predmet sohasini tahlil qilish, konseptual model va relyatsion sxema tuzish, normallashtirish va SQL bilan amalga oshirish.",
        "indicators": [
            {"name": "Loyihalash laboratoriyalari: yechilgan ulushi", "source": S.LABS, "topics": DESIGN_TOPICS, "weight": 2},
            {"name": "Loyihalash mavzulari bo'yicha o'zlashtirish (BKT)", "source": S.MASTERY, "topics": DESIGN_TOPICS},
            {"name": "Loyiha topshiriqlari bo'yicha o'qituvchi bahosi", "source": S.GRADES},
            {"name": "Buyurtmachi talablarini aniqlash (qamrov)", "source": S.INTERVIEW},
        ],
    },
    {
        "name": "Metakognitiv",
        "description": "O'z loyihalash faoliyatini kuzatish va boshqarish: o'z bilimini to'g'ri baholash va yordamga o'rinli murojaat qilish.",
        "indicators": [
            {"name": "O'z bilimini baholash aniqligi (ishonch va natija)", "source": S.CALIBRATION},
            {"name": "Yordamsiz yechish (maslahat so'ramasdan)", "source": S.INDEPENDENCE, "topics": DESIGN_TOPICS},
        ],
    },
    {
        "name": "Refleksiv-baholash",
        "description": "Yechimni asoslash, xatoni topish va tuzatish, boshqa loyihaning sifatini baholash.",
        "indicators": [
            {"name": "Yechimni o'z so'zlari bilan tushuntirish sifati", "source": S.EXPLANATION, "topics": DESIGN_TOPICS},
            {"name": "«Xatoni top» mashqlari: yechilgan ulushi", "source": S.FIND_ERROR, "topics": DESIGN_TOPICS},
            {"name": "Hamkasb ishini baholash aniqligi", "source": S.PEER_ACCURACY},
        ],
    },
]

class Command(BaseCommand):
    help = "Dissertatsiyadagi kompetentlik modelini (4 komponent, 4 daraja) yaratadi va testlarni turiga qarab bog'laydi"

    def add_arguments(self, parser):
        parser.add_argument("--replace", action="store_true", help="Bor modelni o'chirib, qayta yaratish")

    def handle(self, *args, **options):
        if Component.objects.exists() and not options["replace"]:
            raise CommandError("Kompetentlik modeli allaqachon bor. Qayta yaratish uchun --replace qo'shing.")
        quizzes_by_kind = {kind: list(Quiz.objects.filter(kind=kind)) for kind, _ in Quiz.Kind.choices}
        with transaction.atomic():
            Component.objects.all().delete()
            for order, item in enumerate(MODEL, start=1):
                component = Component.objects.create(name=item["name"], description=item["description"], order=order, **LEVELS)
                for indicator_order, data in enumerate(item["indicators"], start=1):
                    indicator = Indicator.objects.create(
                        component=component,
                        name=data["name"],
                        source=data["source"],
                        weight=data.get("weight", 1),
                        topics=data.get("topics", []),
                        order=indicator_order,
                    )
                    for kind in data.get("initial", []):
                        indicator.initial_quizzes.add(*quizzes_by_kind[kind])
                    for kind in data.get("final", []):
                        indicator.final_quizzes.add(*quizzes_by_kind[kind])
                    for kind in data.get("delayed", []):
                        indicator.delayed_quizzes.add(*quizzes_by_kind[kind])
        linked = {kind: len(quizzes_by_kind[kind]) for kind in (Quiz.Kind.PRE, Quiz.Kind.POST, Quiz.Kind.DELAYED)}
        self.stdout.write(
            self.style.SUCCESS(
                f"Yaratildi: {len(MODEL)} komponent. Bog'langan testlar: kirish — {linked['pre']}, "
                f"chiqish — {linked['post']}, kechiktirilgan — {linked['delayed']}."
            )
        )
