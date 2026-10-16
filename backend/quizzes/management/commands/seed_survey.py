"""Tajriba oxiridagi so'rovnomani yaratadi (survey_bank.py).

Ishga tushirish:
    python manage.py seed_survey --author <o'qituvchi> --group <guruh> [--group ...]

AI yoqilgan guruhlarga AI haqidagi savollar bilan to'liq so'rovnoma, nazorat guruhlariga esa
faqat laboratoriya haqidagi savollar bilan alohida so'rovnoma beriladi (umumiy savollar bir xil,
shuning uchun ularni guruhlar o'rtasida solishtirish mumkin).
Qayta ishga tushirilsa, bor so'rovnoma takrorlanmaydi (faqat guruhlar qo'shiladi).
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from users.models import StudentGroup, User

from ...models import Quiz
from ...serializers import QuestionSerializer, QuizSerializer
from ...survey_bank import STATEMENTS, SURVEY_DESCRIPTION, SURVEY_TITLE

VARIANTS = {True: "tajriba guruhi", False: "nazorat guruhi"}


def validated_questions(with_ai):
    data = [{"text": item["text"], "kind": "likert"} for item in STATEMENTS if with_ai or not item["ai"]]
    serializer = QuestionSerializer(data=data, many=True)
    if not serializer.is_valid():
        raise CommandError(f"So'rovnoma savollarida xato: {serializer.errors}")
    return serializer.validated_data


class Command(BaseCommand):
    help = "Tajriba oxiridagi so'rovnomani (Likert shkalasi) yaratadi"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True, help="Muallif (o'qituvchi yoki admin logini)")
        parser.add_argument("--group", action="append", default=[], help="Biriktiriladigan guruh nomi")

    def handle(self, *args, **options):
        try:
            author = User.objects.get(username=options["author"])
        except User.DoesNotExist:
            raise CommandError(f"Bunday foydalanuvchi yo'q: {options['author']}")
        if author.is_student:
            raise CommandError("So'rovnoma muallifi talaba bo'la olmaydi.")
        groups = list(StudentGroup.objects.filter(name__in=options["group"]))
        missing = set(options["group"]) - {group.name for group in groups}
        if missing:
            raise CommandError(f"Bunday guruh yo'q: {', '.join(sorted(missing))}")
        if not groups:
            raise CommandError("Kamida bitta --group ko'rsating.")

        with transaction.atomic():
            for with_ai, variant in VARIANTS.items():
                selected = [group for group in groups if group.ai_enabled == with_ai]
                if not selected:
                    continue
                title = f"{SURVEY_TITLE} ({variant})"
                quiz = Quiz.objects.filter(title=title, author=author).first()
                if quiz:
                    self.stdout.write(f"«{title}» allaqachon bor: faqat guruhlar qo'shildi.")
                else:
                    quiz = Quiz.objects.create(
                        kind=Quiz.Kind.SURVEY, title=title, description=SURVEY_DESCRIPTION, author=author
                    )
                    QuizSerializer.write_questions(quiz, validated_questions(with_ai))
                    self.stdout.write(self.style.SUCCESS(f"«{title}» yaratildi: {quiz.questions.count()} ta savol."))
                quiz.groups.add(*selected)
