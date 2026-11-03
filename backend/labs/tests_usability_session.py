"""prepare_usability_session: guruh, hisoblar, laboratoriyalar, imtihon vaqti, SUS va login kartochkalari."""
import os
import re
import tempfile
from datetime import timedelta
from io import StringIO

from django.contrib.auth import authenticate
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from quizzes.models import Quiz
from users.models import StudentGroup, User

from .models import Lab
from .tests import ER_REFERENCE


class PrepareUsabilitySessionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user("ps_teacher", role=User.Role.TEACHER)
        kw = {"kind": Lab.Kind.ER, "description": "shart", "reference_diagram": ER_REFERENCE, "author": cls.teacher}
        cls.learn = Lab.objects.create(title="ER-model 2. Kutubxona", **kw)
        cls.exam = Lab.objects.create(title="ER-model 3. Shifoxona: 1:1, 1:N va M:N", **kw)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cards = os.path.join(self.tmp.name, "kartochkalar.html")

    def tearDown(self):
        self.tmp.cleanup()

    def run_command(self, *extra, **options):
        args = ["--author", "ps_teacher", "--group", "FS-T", "--count", "3", "--start", "2026-11-20 10:00",
                "--cards", self.cards, *extra]
        out = StringIO()
        call_command("prepare_usability_session", *args, stdout=out, **options)
        return out.getvalue()

    def test_creates_session(self):
        out = self.run_command("--url", "https://mb.example.uz")
        group = StudentGroup.objects.get(name="FS-T")
        self.assertTrue(group.ai_enabled)
        self.assertFalse(group.in_study)
        self.assertIn(self.teacher, group.teachers.all())
        students = list(group.students.order_by("username"))
        self.assertEqual([s.username for s in students], ["fs01", "fs02", "fs03"])

        learn, exam = Lab.objects.filter(groups=group).order_by("pk")
        self.assertEqual((learn.title, learn.module), ("FS-T: ER-model 2. Kutubxona", None))
        self.assertEqual(learn.reference_diagram, ER_REFERENCE)
        self.assertTrue(exam.title.startswith("FS-T: ER-model 3. Shifoxona"))
        start = timezone.localtime(exam.module.exam_starts_at)
        self.assertEqual((start.hour, start.minute), (10, 45))
        self.assertEqual(exam.module.exam_ends_at - exam.module.exam_starts_at, timedelta(minutes=25))
        # Manbalar o'zgarmagan
        self.assertEqual(Lab.objects.get(pk=self.learn.pk).title, "ER-model 2. Kutubxona")
        self.assertFalse(self.learn.groups.exists())

        sus = Quiz.objects.get(title__startswith="Platformadan foydalanish", groups=group)
        self.assertEqual(sus.questions.count(), 10)
        self.assertIn(f"--learn-lab {learn.pk} --exam-lab {exam.pk} --sus {sus.pk}", out)

        cards = open(self.cards, encoding="utf-8").read()
        self.assertIn("https://mb.example.uz", cards)
        for index, student in enumerate(students, start=1):
            self.assertIn(f"FS-{index:02d}", cards)
            password = re.search(rf"<code>{student.username}</code>.*?Parol</span><code>([^<]+)</code>", cards, re.S).group(1)
            self.assertEqual(len(password), 10)
            self.assertEqual(authenticate(username=student.username, password=password), student)

    def test_passwords_are_unique_and_unambiguous(self):
        self.run_command("--count", "10")
        cards = open(self.cards, encoding="utf-8").read()
        passwords = re.findall(r"Parol</span><code>([^<]+)</code>", cards)
        self.assertEqual(len(set(passwords)), 10)
        self.assertFalse(any(ch in p for p in passwords for ch in "0O1lI"))

    def test_rejects_existing_group_and_taken_logins(self):
        self.run_command()
        with self.assertRaisesMessage(CommandError, "allaqachon bor"):
            self.run_command()
        with self.assertRaisesMessage(CommandError, "band: fs01, fs02, fs03"):
            self.run_command("--group", "FS-T2")
        self.assertFalse(StudentGroup.objects.filter(name="FS-T2").exists())

    def test_validates_arguments(self):
        with self.assertRaisesMessage(CommandError, "YYYY-MM-DD HH:MM"):
            self.run_command("--start", "20.11.2026")
        with self.assertRaisesMessage(CommandError, "1 dan 60"):
            self.run_command("--count", "0")
        with self.assertRaisesMessage(CommandError, "turli bo'lishi"):
            self.run_command("--learn-lab", str(self.learn.pk), "--exam-lab", str(self.learn.pk))
        self.assertFalse(StudentGroup.objects.filter(name="FS-T").exists())
