"""Namunaviy kompetentlik modelini yaratadi: 4 komponent va ularning ko'rsatkichlari.

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

MODEL = [
    {
        "name": "Motivatsion-qadriyatli",
        "description": "Ma'lumotlar bazasini loyihalashga qiziqish, uning kasbiy ahamiyatini anglash va o'z kuchiga ishonch.",
        "indicators": [
            {"name": "So'rovnomadagi munosabat (Likert)", "source": S.SURVEY, "initial": [], "final": [Quiz.Kind.SURVEY]},
        ],
    },
    {
        "name": "Kognitiv",
        "description": "Konseptual model, kalitlar, bog'lanishlar, normallashtirish va cheklovlar bo'yicha bilimlar.",
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
        "name": "Faoliyatli (amaliy)",
        "description": "ER-model tuzish, jadvallarni loyihalash, normallashtirish va SQL bilan amalga oshirish ko'nikmalari.",
        "indicators": [
            {"name": "Loyihalash laboratoriyalari: yechilgan ulushi", "source": S.LABS, "topics": DESIGN_TOPICS, "weight": 2},
            {"name": "Barcha mavzular bo'yicha o'zlashtirish (BKT)", "source": S.MASTERY},
            {"name": "Loyiha topshiriqlari bo'yicha o'qituvchi bahosi", "source": S.GRADES},
            {"name": "Buyurtmachi talablarini aniqlash (qamrov)", "source": S.INTERVIEW},
        ],
    },
    {
        "name": "Refleksiv",
        "description": "O'z yechimini tushuntira olish, xatolarini tahlil qilish va o'z faoliyatini baholash.",
        "indicators": [
            {"name": "Yechimni o'z so'zlari bilan tushuntirish sifati", "source": S.EXPLANATION, "topics": DESIGN_TOPICS},
            {"name": "O'z bilimini baholash aniqligi (ishonch va natija)", "source": S.CALIBRATION},
        ],
    },
]


class Command(BaseCommand):
    help = "Namunaviy kompetentlik modelini (4 komponent) yaratadi va testlarni turiga qarab bog'laydi"

    def add_arguments(self, parser):
        parser.add_argument("--replace", action="store_true", help="Bor modelni o'chirib, qayta yaratish")

    def handle(self, *args, **options):
        if Component.objects.exists() and not options["replace"]:
            raise CommandError("Kompetentlik modeli allaqachon bor. Qayta yaratish uchun --replace qo'shing.")
        quizzes_by_kind = {kind: list(Quiz.objects.filter(kind=kind)) for kind, _ in Quiz.Kind.choices}
        with transaction.atomic():
            Component.objects.all().delete()
            for order, item in enumerate(MODEL, start=1):
                component = Component.objects.create(name=item["name"], description=item["description"], order=order)
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
        linked = {kind: len(quizzes_by_kind[kind]) for kind in (Quiz.Kind.PRE, Quiz.Kind.POST, Quiz.Kind.DELAYED, Quiz.Kind.SURVEY)}
        self.stdout.write(
            self.style.SUCCESS(
                f"Yaratildi: {len(MODEL)} komponent. Bog'langan testlar: kirish — {linked['pre']}, "
                f"chiqish — {linked['post']}, kechiktirilgan — {linked['delayed']}, so'rovnoma — {linked['survey']}."
            )
        )
