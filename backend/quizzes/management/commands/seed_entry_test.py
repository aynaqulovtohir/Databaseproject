"""Kirish, chiqish va kechiktirilgan testlarni bir xil savollar bilan yaratadi (question_bank.py).

Ishga tushirish:
    python manage.py seed_entry_test --author <o'qituvchi> --group <guruh> [--group ...]
        [--kind pre|post|delayed|both] [--time-limit 30]
    python manage.py seed_entry_test --markdown     # savollar va javoblar kaliti (dissertatsiya ilovasi uchun)

Kechiktirilgan test (--kind delayed) kurs tugagandan bir necha hafta keyin o'sha savollar bilan o'tkaziladi:
bilim qanchalik saqlanganini o'lchaydi; ochilish vaqtini keyinga qo'ying.
Qayta ishga tushirilsa, bor test takrorlanmaydi (faqat guruhlar qo'shiladi).
Testlar sukut bo'yicha darhol ochiq; ochilish vaqtini o'qituvchi sahifada belgilaydi.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from users.models import StudentGroup, User

from ...models import Quiz
from ...question_bank import QUESTIONS, TEST_DESCRIPTION, TEST_TITLE
from ...serializers import QuestionSerializer, QuizSerializer

KIND_TITLES = {"pre": "kirish testi", "post": "chiqish testi", "delayed": "kechiktirilgan test"}
LETTERS = "ABCDEFGHIJ"


def validated_questions():
    """Savollar API dagi qoidalar bilan tekshiriladi (masalan, bitta javobli savolda aynan bitta to'g'ri variant)."""
    serializer = QuestionSerializer(data=[{k: v for k, v in q.items() if k != "topic"} for q in QUESTIONS], many=True)
    if not serializer.is_valid():
        raise CommandError(f"Savollar bankida xato: {serializer.errors}")
    return serializer.validated_data


def markdown():
    lines = [f"# {TEST_TITLE}: kirish va chiqish testi", "", TEST_DESCRIPTION, ""]
    lines += [f"Savollar soni: {len(QUESTIONS)}. Har bir savol 1 ball.", ""]
    lines += [
        "Bir nechta to'g'ri javobli savollarda ball qisman beriladi: (to'g'ri belgilanganlar − noto'g'ri belgilanganlar) / "
        "to'g'ri variantlar soni, manfiy bo'lmaydi. Talabaga variantlar aralashtirilgan tartibda ko'rsatiladi.",
        "",
    ]
    key = []
    for number, question in enumerate(QUESTIONS, start=1):
        kind = "bitta to'g'ri javob" if question["kind"] == "single" else "bir nechta to'g'ri javob"
        lines += [f"## {number}. {question['text']}", "", f"*Mavzu: {question['topic']} · {kind}*", ""]
        correct = []
        for index, choice in enumerate(question["choices"]):
            lines.append(f"{LETTERS[index]}) {choice['text']}")
            if choice["is_correct"]:
                correct.append(LETTERS[index])
        lines.append("")
        key.append(f"| {number} | {question['topic']} | {', '.join(correct)} |")
    lines += ["## Javoblar kaliti", "", "| № | Mavzu | To'g'ri javob |", "|---|---|---|", *key, ""]
    return "\n".join(lines)


class Command(BaseCommand):
    help = "Kirish, chiqish (va kechiktirilgan) testlarini bir xil savollar bilan yaratadi"

    def add_arguments(self, parser):
        parser.add_argument("--author", help="Test muallifi (o'qituvchi yoki admin logini)")
        parser.add_argument("--group", action="append", default=[], help="Biriktiriladigan guruh nomi")
        parser.add_argument("--kind", choices=["pre", "post", "delayed", "both"], default="both")
        parser.add_argument("--time-limit", type=int, default=30, help="Vaqt chegarasi, daqiqa (0 — cheklanmagan)")
        parser.add_argument("--markdown", action="store_true", help="Savollar va javoblar kalitini Markdown'da chiqarish")

    def handle(self, *args, **options):
        questions = validated_questions()
        if options["markdown"]:
            self.stdout.write(markdown())
            return
        if not options["author"]:
            raise CommandError("--author ko'rsatilishi kerak.")
        try:
            author = User.objects.get(username=options["author"])
        except User.DoesNotExist:
            raise CommandError(f"Bunday foydalanuvchi yo'q: {options['author']}")
        if author.is_student:
            raise CommandError("Test muallifi talaba bo'la olmaydi.")
        groups = list(StudentGroup.objects.filter(name__in=options["group"]))
        missing = set(options["group"]) - {group.name for group in groups}
        if missing:
            raise CommandError(f"Bunday guruh yo'q: {', '.join(sorted(missing))}")
        if not groups:
            raise CommandError("Kamida bitta --group ko'rsating.")

        kinds = ["pre", "post"] if options["kind"] == "both" else [options["kind"]]
        with transaction.atomic():
            for kind in kinds:
                title = f"{TEST_TITLE}: {KIND_TITLES[kind]}"
                quiz = Quiz.objects.filter(title=title, author=author).first()
                if quiz:
                    self.stdout.write(f"«{title}» allaqachon bor: faqat guruhlar qo'shildi.")
                else:
                    quiz = Quiz.objects.create(
                        kind=kind,
                        title=title,
                        description=TEST_DESCRIPTION,
                        author=author,
                        time_limit_minutes=options["time_limit"] or None,
                        show_answers=False,
                    )
                    # Har bir test o'z nusxasini oladi (write_questions lug'atlarni o'zgartiradi)
                    QuizSerializer.write_questions(quiz, [{**q, "choices": list(q["choices"])} for q in questions])
                    self.stdout.write(self.style.SUCCESS(f"«{title}» yaratildi: {quiz.questions.count()} ta savol."))
                quiz.groups.add(*groups)
