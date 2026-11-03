"""Foydalanish sinovi hisoboti: T1–T7 loglardan, log to'liqligi ikki ta'rifda, AI va baho manbasi."""
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from quizzes.models import Quiz, QuizAttempt
from users.models import StudentGroup, User

from .models import ErSnapshot, Lab, LabAttempt, LabChatMessage, LabGrade
from .tests import ER_REFERENCE
from .usability import report

SMALL = {"entities": [{"id": "a", "name": "A", "x": 0, "y": 0, "attributes": [{"key": "pk", "name": "id"}]}], "relationships": []}


def big(extra=""):
    names = ["Talaba", "Guruh", "Fan"]
    return {
        "entities": [{"id": n.lower(), "name": n + extra, "x": 0, "y": 0, "attributes": [{"key": "pk", "name": "id"}]} for n in names],
        "relationships": [
            {"id": "r1", "name": "", "source": "talaba", "target": "guruh", "source_card": "N", "target_card": "1"},
            {"id": "r2", "name": "", "source": "talaba", "target": "fan", "source_card": "N", "target_card": "N"},
        ],
    }


class UsabilityReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user("u_teacher", role=User.Role.TEACHER)
        cls.group = StudentGroup.objects.create(name="FS-TEST", ai_enabled=True)
        cls.other = StudentGroup.objects.create(name="BOSHQA")
        kw = {"kind": Lab.Kind.ER, "description": "d", "reference_diagram": ER_REFERENCE, "author": cls.teacher}
        cls.learn = Lab.objects.create(title="O'quv ER", **kw)
        cls.exam = Lab.objects.create(title="Imtihon ER", **kw)
        call_command("seed_sus", "--author", "u_teacher", "--group", "FS-TEST", stdout=StringIO())
        cls.sus = Quiz.objects.get(title__startswith="Platformadan foydalanish")
        cls.t0 = timezone.now() - timedelta(hours=1)

    def at(self, obj, minutes):
        type(obj).objects.filter(pk=obj.pk).update(created_at=self.t0 + timedelta(minutes=minutes))

    def snap(self, student, lab, diagram, minutes):
        self.at(ErSnapshot.objects.create(student=student, lab=lab, diagram=diagram), minutes)

    def attempt(self, student, lab, diagram, minutes, submission=False, hints=()):
        a = LabAttempt.objects.create(student=student, lab=lab, diagram=diagram, is_correct=False,
                                      is_submission=submission, ai_hints=list(hints))
        self.at(a, minutes)
        if submission:
            LabGrade.objects.create(student=student, lab=lab, attempt=a, score=50, source=LabGrade.Source.AUTO)
        return a

    def sus_answers(self, student, count):
        answers = {}
        for question in self.sus.questions.order_by("order")[:count]:
            answers[str(question.pk)] = [question.choices.get(order=3).pk]
        QuizAttempt.objects.create(quiz=self.sus, student=student, answers=answers, submitted_at=timezone.now())

    def full_student(self, name):
        s = User.objects.create_user(name, role=User.Role.STUDENT, group=self.group, research_consent=True)
        for minute in range(1, 4):
            self.snap(s, self.learn, SMALL, minute)
        self.attempt(s, self.learn, SMALL, 4, hints=["maslahat"])
        for minute in range(5, 8):
            self.snap(s, self.learn, big(), minute)
        self.attempt(s, self.learn, big(), 9, submission=True)
        for minute in range(10, 15):
            self.snap(s, self.exam, big(" "), minute)
        self.attempt(s, self.exam, big(" "), 15, submission=True)
        self.sus_answers(s, 10)
        return s

    def test_full_student_completes_all_tasks(self):
        s = self.full_student("u_full")
        row = report([s], self.learn, self.exam, self.sus)["rows"][0]
        self.assertEqual(row["tasks"], {t: 2 for t in ("T1", "T2", "T3", "T4", "T5", "T6", "T7")})
        self.assertEqual(row["snapshots"], (6, 5))
        self.assertEqual(row["logs"], [(True, True), (True, True)])
        self.assertEqual(row["learn_minutes"], 8.0)

    def test_missing_steps_are_zero(self):
        s = User.objects.create_user("u_partial", role=User.Role.STUDENT, group=self.group)  # rozilik qarori yo'q
        self.snap(s, self.learn, SMALL, 1)
        self.attempt(s, self.learn, big(), 2, submission=True)  # tekshiruvsiz; oxirgi holat topshirilganga teng emas
        self.sus_answers(s, 9)
        row = report([s], self.learn, self.exam, self.sus)["rows"][0]
        self.assertEqual(row["tasks"], {"T1": 0, "T2": 0, "T3": 0, "T4": 0, "T5": 2, "T6": 0, "T7": 0})
        self.assertEqual(row["logs"], [(False, False), (False, False)])

    def test_coach_question_counts_for_t4_and_summary(self):
        s = self.full_student("u_coach")
        LabAttempt.objects.filter(student=s).update(ai_hints=[])
        LabChatMessage.objects.create(student=s, lab=self.learn, role=LabChatMessage.Role.USER, content="savol")
        LabChatMessage.objects.create(student=s, lab=self.learn, role=LabChatMessage.Role.ASSISTANT, content="javob")
        no_ai = self.full_student("u_noai")
        LabAttempt.objects.filter(student=no_ai).update(ai_hints=[])
        data = report([s, no_ai], self.learn, self.exam, self.sus)
        self.assertEqual(data["rows"][0]["tasks"]["T4"], 2)
        self.assertEqual(data["rows"][1]["tasks"]["T4"], 0)
        self.assertEqual(data["ai"], {"hints": 0, "coach_questions": 1, "users": 1})
        self.assertEqual(data["tasks"]["T4"], {"done": 1, "n": 2})
        self.assertEqual(data["logs"], {"works": 4, "enough_snapshots": 4, "reconstructed": 4, "min_snapshots": 5})
        self.assertEqual(data["grade_sources"], {"auto": 2})

    def test_without_sus_t7_is_not_counted(self):
        s = self.full_student("u_nosus")
        data = report([s], self.learn, self.exam)
        self.assertIsNone(data["rows"][0]["tasks"]["T7"])
        self.assertEqual(data["tasks"]["T7"], {"done": 0, "n": 0})

    def test_command_uses_group_and_pseudonyms(self):
        self.full_student("u_cmd")
        User.objects.create_user("u_other", role=User.Role.STUDENT, group=self.other, first_name="Begona")
        out = StringIO()
        call_command("usability_report", "--group", "FS-TEST", "--learn-lab", str(self.learn.pk),
                     "--exam-lab", str(self.exam.pk), "--sus", str(self.sus.pk), stdout=out)
        text = out.getvalue()
        self.assertIn("talabalar: 1", text)
        self.assertIn("FS-01", text)
        self.assertNotIn("Begona", text)
        self.assertIn("T7: 1/1 (100%)", text)

    def test_command_rejects_unknown_group_and_non_er_lab(self):
        with self.assertRaises(CommandError):
            call_command("usability_report", "--group", "yoq", "--learn-lab", "1", "--exam-lab", "1", stdout=StringIO())
        sql = Lab.objects.create(title="SQL", description="d", author=self.teacher)
        with self.assertRaises(CommandError):
            call_command("usability_report", "--group", "FS-TEST", "--learn-lab", str(sql.pk),
                         "--exam-lab", str(self.exam.pk), stdout=StringIO())
