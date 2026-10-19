"""Brauzer (Playwright) testlari uchun alohida bazani noldan tayyorlaydi: migratsiya va test ma'lumotlari.

Ishga tushirish (docker-compose.e2e.yml buni o'zi qiladi):
    E2E=1 POSTGRES_DB=dbproject_e2e python manage.py seed_e2e

Parollari ma'lum hisoblar yaratadi, shuning uchun faqat E2E=1 bo'lsa va baza nomi "_e2e" bilan tugasa ishlaydi:
ishchi yoki ishlab chiqish bazasida tasodifan ishga tushib qolmaydi. Baza har safar o'chirilib qayta yaratiladi.
Loginlar va parollar frontend/e2e/accounts.ts dagi bilan bir xil bo'lishi kerak.
"""
import os
from datetime import timedelta

import psycopg
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import connection
from psycopg import sql

from labs.evolution_labs import EVOLUTION_LABS
from labs.integrity_labs import INTEGRITY_LABS
from labs.models import Lab, LabModule
from labs.probes import validate_probes
from labs.reverse import diagram_from_sql
from labs.reverse_labs import REVERSE_LABS
from quizzes.models import Quiz
from quizzes.serializers import QuizSerializer
from users.consent import CONSENT_VERSION
from users.models import StudentGroup, User

PASSWORD = "e2e-Parol-2026"
ACCOUNTS = [
    # (login, rol, ism, familiya, tadqiqotga rozilik: None — hali so'ralmagan)
    ("e2e_admin", User.Role.ADMIN, "Admin", "Sinov", None),
    ("e2e_teacher", User.Role.TEACHER, "O'qituvchi", "Sinov", None),
    ("e2e_student", User.Role.STUDENT, "Talaba", "Sinov", True),
    ("e2e_newcomer", User.Role.STUDENT, "Yangi", "Talaba", None),
]
GROUP = "E2E-guruh"
EXAM_MODULE_TITLE = "E2E: imtihon moduli"
EXAM_LAB_TITLE = "E2E: imtihon laboratoriyasi"
ER_LAB_TITLE = "E2E: ER-diagramma"
ER_REFERENCE = {
    "entities": [{"id": "t", "name": "Talaba", "x": 0, "y": 0, "attributes": [{"name": "id", "key": "pk"}]}],
    "relationships": [],
}
QUIZ_TITLE = "E2E: normallashtirish"
QUESTIONS = [
    {
        "kind": "single",
        "text": "Qaysi normal shakl tranzitiv bog'liqliklarni yo'qotadi?",
        "points": 1,
        "choices": [
            {"text": "1NF", "is_correct": False},
            {"text": "2NF", "is_correct": False},
            {"text": "3NF", "is_correct": True},
        ],
    },
    {
        "kind": "single",
        "text": "Birlamchi kalit NULL qiymat qabul qila oladimi?",
        "points": 1,
        "choices": [
            {"text": "Ha", "is_correct": False},
            {"text": "Yo'q", "is_correct": True},
        ],
    },
]


class Command(BaseCommand):
    help = "Playwright testlari uchun alohida bazani noldan tayyorlaydi (faqat E2E=1 va *_e2e baza)"
    # Baza hali yo'q bo'lishi mumkin: tekshiruvlar bazaga ulanmasin
    requires_system_checks = []

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        if os.environ.get("E2E") != "1" or not db["NAME"].endswith("_e2e"):
            raise CommandError("Faqat E2E=1 va nomi '_e2e' bilan tugaydigan baza uchun ishlaydi.")
        self.recreate_database(db)
        call_command("migrate", verbosity=0)
        call_command("createcachetable", verbosity=0)
        self.seed()
        self.stdout.write(self.style.SUCCESS(f"E2E bazasi tayyor: {db['NAME']}"))

    def recreate_database(self, db):
        connection.close()
        with psycopg.connect(
            dbname="postgres", user=db["USER"], password=db["PASSWORD"], host=db["HOST"], port=db["PORT"], autocommit=True
        ) as maintenance:
            name = sql.Identifier(db["NAME"])
            maintenance.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(name))
            maintenance.execute(sql.SQL("CREATE DATABASE {}").format(name))

    def seed(self):
        group = StudentGroup.objects.create(name=GROUP)
        users = {}
        for username, role, first_name, last_name, consent in ACCOUNTS:
            user = User(username=username, role=role, first_name=first_name, last_name=last_name)
            user.set_password(PASSWORD)
            if role == User.Role.STUDENT:
                user.group = group
            if consent is not None:
                user.research_consent = consent
                user.research_consent_version = CONSENT_VERSION
            user.save()
            users[username] = user
        group.teachers.add(users["e2e_teacher"])

        quiz = Quiz.objects.create(
            kind=Quiz.Kind.PRACTICE, title=QUIZ_TITLE, author=users["e2e_teacher"], show_answers=True
        )
        QuizSerializer.write_questions(quiz, [{**q, "choices": list(q["choices"])} for q in QUESTIONS])
        quiz.groups.add(group)

        lab = Lab.objects.create(
            kind=Lab.Kind.ER,
            title=ER_LAB_TITLE,
            description="Talaba obyektini chizing.",
            reference_diagram=ER_REFERENCE,
            author=users["e2e_teacher"],
        )
        lab.groups.add(group)

        integrity = INTEGRITY_LABS[0]
        lab = Lab.objects.create(
            **{**integrity, "probes": validate_probes(integrity["probes"])}, author=users["e2e_teacher"]
        )
        lab.groups.add(group)

        reverse = REVERSE_LABS[0]
        lab = Lab.objects.create(
            **reverse, reference_diagram=diagram_from_sql(reverse["setup_sql"]), author=users["e2e_teacher"]
        )
        lab.groups.add(group)

        lab = Lab.objects.create(**EVOLUTION_LABS[0], author=users["e2e_teacher"])
        lab.groups.add(group)

        # Davom etayotgan imtihon: AI yordami o'chirilgan modul
        now = timezone.now()
        exam = LabModule.objects.create(
            title=EXAM_MODULE_TITLE, sequential=False, author=users["e2e_teacher"],
            exam_starts_at=now - timedelta(hours=1), exam_ends_at=now + timedelta(hours=2),
        )
        lab = Lab.objects.create(
            title=EXAM_LAB_TITLE,
            description="Barcha kitoblar nomini chiqaring.",
            setup_sql="CREATE TABLE kitob (id INT PRIMARY KEY, nomi TEXT); INSERT INTO kitob VALUES (1, 'Alifbo');",
            solution_sql="SELECT nomi FROM kitob;",
            author=users["e2e_teacher"],
            module=exam,
        )
        lab.groups.add(group)
