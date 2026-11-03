"""SUS (foydalanish qulayligi) so'rovnomasini yaratadi (sus_bank.py).

Ishga tushirish:
    python manage.py seed_sus --author <o'qituvchi> --group <guruh> [--group ...]

Qayta ishga tushirilsa, bor so'rovnoma takrorlanmaydi (faqat guruhlar qo'shiladi).
Natija: python manage.py sus_report --quiz <id>
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from users.models import StudentGroup, User

from ...models import Quiz
from ...serializers import QuestionSerializer, QuizSerializer
from ...sus_bank import SUS_DESCRIPTION, SUS_ITEMS, SUS_TITLE


def validated_questions():
    serializer = QuestionSerializer(data=[{"text": text, "kind": "likert"} for text in SUS_ITEMS], many=True)
    if not serializer.is_valid():
        raise CommandError(f"SUS savollarida xato: {serializer.errors}")
    return serializer.validated_data


class Command(BaseCommand):
    help = "SUS foydalanish qulayligi so'rovnomasini (10 ta fikr, Likert 1-5) yaratadi"

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
            quiz = Quiz.objects.filter(title=SUS_TITLE, author=author, kind=Quiz.Kind.SURVEY).first()
            if quiz:
                self.stdout.write(f"«{SUS_TITLE}» allaqachon bor (id {quiz.pk}): faqat guruhlar qo'shildi.")
            else:
                quiz = Quiz.objects.create(kind=Quiz.Kind.SURVEY, title=SUS_TITLE, description=SUS_DESCRIPTION, author=author)
                QuizSerializer.write_questions(quiz, validated_questions())
                self.stdout.write(self.style.SUCCESS(f"«{SUS_TITLE}» yaratildi (id {quiz.pk}): {quiz.questions.count()} ta fikr."))
            quiz.groups.add(*groups)
