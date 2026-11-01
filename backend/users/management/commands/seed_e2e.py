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
from django.db.models import Q
from django.utils import timezone
from django.db import connection
from psycopg import sql

from labs.evolution_labs import EVOLUTION_LABS
from labs.integrity_labs import INTEGRITY_LABS
from labs.models import AIAction, Lab, LabModule
from labs.probes import validate_probes
from labs.reverse import diagram_from_sql
from labs.reverse_labs import REVERSE_LABS
from quizzes.models import Quiz, QuizAttempt
from quizzes.serializers import QuizSerializer
from quizzes.survey_bank import EXTERNAL_AI_TEXTS
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
STEPS_LAB_TITLE = "E2E: bajarish tartibi"
ER_REFERENCE = {
    "entities": [{"id": "t", "name": "Talaba", "x": 0, "y": 0, "attributes": [{"name": "id", "key": "pk"}]}],
    "relationships": [],
}
# Pilot (e2e/pilot.spec.ts): to'liq tajriba yo'li. Har bir shartda ikkita guruh; guruhdagi tayyor talabalar (kirish, chiqish)
# natijalari tahlil kartasi to'lishi uchun, brauzerda yo'lni pilot_ai va pilot_nazorat bosib o'tadi
PILOT_LAB_TITLE = "Pilot: kitoblar ro'yxati"
PILOT_GROUPS = [
    ("Pilot-AI-1", True, [35, 42, 50, 28, 60, 45], [58, 66, 72, 47, 80, 61]),
    ("Pilot-AI-2", True, [38, 47, 55, 30, 52, 41], [55, 70, 68, 52, 77, 60]),
    ("Pilot-Nazorat-1", False, [36, 44, 49, 29, 58, 46], [44, 52, 58, 35, 66, 50]),
    ("Pilot-Nazorat-2", False, [40, 45, 53, 31, 51, 42], [50, 49, 60, 38, 62, 51]),
]
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

        lab = Lab.objects.create(
            title=STEPS_LAB_TITLE,
            description="Barcha kitoblar nomini chiqaring.",
            setup_sql="CREATE TABLE kitob (id INT PRIMARY KEY, nomi TEXT); INSERT INTO kitob VALUES (1, 'Alifbo');",
            solution_sql="SELECT nomi FROM kitob;",
            author=users["e2e_teacher"],
        )
        lab.groups.add(group)

        # Davom etayotgan imtihon: AI yordami o'chirilgan modul
        now = timezone.now()
        exam = LabModule.objects.create(
            title=EXAM_MODULE_TITLE, sequential=False, author=users["e2e_teacher"],
            exam_starts_at=now - timedelta(hours=1), exam_ends_at=now + timedelta(hours=2),
        )
        self.seed_pilot(users["e2e_teacher"], now)

        lab = Lab.objects.create(
            title=EXAM_LAB_TITLE,
            description="Barcha kitoblar nomini chiqaring.",
            setup_sql="CREATE TABLE kitob (id INT PRIMARY KEY, nomi TEXT); INSERT INTO kitob VALUES (1, 'Alifbo');",
            solution_sql="SELECT nomi FROM kitob;",
            author=users["e2e_teacher"],
            module=exam,
        )
        lab.groups.add(group)

    def seed_pilot(self, teacher, now):
        groups = {}
        for name, ai_enabled, _, _ in PILOT_GROUPS:
            groups[name] = StudentGroup.objects.create(name=name, ai_enabled=ai_enabled)
            groups[name].teachers.add(teacher)
        names = ["--group=" + name for name in groups]
        call_command("seed_entry_test", "--author", teacher.username, *names, verbosity=0, stdout=self.stdout)
        call_command("seed_survey", "--author", teacher.username, *names, verbosity=0, stdout=self.stdout)
        lab = Lab.objects.create(
            title=PILOT_LAB_TITLE,
            description="Barcha kitoblar nomini chiqaring.",
            setup_sql="CREATE TABLE kitob (id INT PRIMARY KEY, nomi TEXT); INSERT INTO kitob VALUES (1, 'Alifbo');",
            solution_sql="SELECT nomi FROM kitob;",
            author=teacher,
        )
        lab.groups.add(*groups.values())

        # Brauzerda yo'lni bosib o'tadigan talabalar: rozilik hali so'ralmagan
        for username, group, first_name in (("pilot_ai", "Pilot-AI-1", "Tajriba"), ("pilot_nazorat", "Pilot-Nazorat-1", "Nazorat")):
            user = User(username=username, role=User.Role.STUDENT, first_name=first_name, last_name="Pilot", group=groups[group])
            user.set_password(PASSWORD)
            user.save()

        pre = Quiz.objects.get(author=teacher, kind=Quiz.Kind.PRE)
        post = Quiz.objects.get(author=teacher, kind=Quiz.Kind.POST)
        surveys = {quiz.groups.first().ai_enabled: quiz for quiz in Quiz.objects.filter(author=teacher, kind=Quiz.Kind.SURVEY)}
        for name, ai_enabled, pres, posts in PILOT_GROUPS:
            for index, (pre_score, post_score) in enumerate(zip(pres, posts)):
                student = User(
                    username=f"{name.lower()}-{index}", role=User.Role.STUDENT, group=groups[name], first_name="MAXFIY-ISM",
                    research_consent=True, research_consent_version=CONSENT_VERSION,
                )
                student.set_unusable_password()
                student.save()
                self.pilot_attempt(pre, student, pre_score, now - timedelta(days=30))
                self.pilot_attempt(post, student, post_score, now - timedelta(days=1))
                # Har guruhda oxirgi talaba AI dan foydalanmagan, qolganlarining dozasi har xil
                if ai_enabled and index < len(pres) - 1:
                    for _ in range(index + 1):
                        action = AIAction.objects.create(student=student, kind=AIAction.Kind.LAB_CHAT)
                        AIAction.objects.filter(pk=action.pk).update(created_at=now - timedelta(days=5))
                self.pilot_survey(surveys[ai_enabled], student, 2 if index else 4, now)
            # Faqat kirish testini topshirib tashlab ketgan talaba
            dropped = User(
                username=f"{name.lower()}-ketgan", role=User.Role.STUDENT, group=groups[name], first_name="MAXFIY-ISM",
                research_consent=True, research_consent_version=CONSENT_VERSION,
            )
            dropped.set_unusable_password()
            dropped.save()
            self.pilot_attempt(pre, dropped, 33, now - timedelta(days=30))

    @staticmethod
    def pilot_attempt(quiz, student, score, moment):
        attempt = QuizAttempt.objects.create(quiz=quiz, student=student, answers={}, results={}, score=score, max_score=100, submitted_at=moment)
        QuizAttempt.objects.filter(pk=attempt.pk).update(started_at=moment - timedelta(minutes=20))

    @staticmethod
    def pilot_survey(quiz, student, external, now):
        """Likert javoblari: umumiy savollarga 4, tashqi AI savollariga external."""
        answers = {}
        for question in quiz.questions.prefetch_related("choices").filter(Q(kind="likert")):
            value = external if question.text in EXTERNAL_AI_TEXTS else 4
            answers[str(question.pk)] = [choice.pk for choice in question.choices.all() if choice.order == value]
        QuizAttempt.objects.create(quiz=quiz, student=student, answers=answers, results={}, submitted_at=now - timedelta(hours=20))
