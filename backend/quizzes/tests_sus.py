"""SUS so'rovnomasi: yaratish, hisoblash (Brooke, 1996) va guruh bo'yicha natija."""
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from users.models import StudentGroup, User

from .models import Quiz, QuizAttempt
from .sus import acceptability, grade, item_contribution, report, score, summarize
from .sus_bank import SUS_ITEMS, SUS_TITLE


class SusScoringTests(SimpleTestCase):
    def test_item_direction(self):
        # Toq — ijobiy (javob − 1), juft — salbiy (5 − javob)
        self.assertEqual((item_contribution(1, 5), item_contribution(2, 5)), (4, 0))
        self.assertEqual((item_contribution(9, 1), item_contribution(10, 1)), (0, 4))

    def test_known_scores(self):
        self.assertEqual(score({order: 3 for order in range(1, 11)}), 50.0)
        best = {order: 5 if order % 2 else 1 for order in range(1, 11)}
        worst = {order: 1 if order % 2 else 5 for order in range(1, 11)}
        self.assertEqual((score(best), score(worst)), (100.0, 0.0))
        self.assertEqual(score({order: 4 if order % 2 else 2 for order in range(1, 11)}), 75.0)

    def test_incomplete_is_not_scored(self):
        values = {order: 3 for order in range(1, 11)}
        values[7] = None
        self.assertIsNone(score(values))
        del values[7]
        self.assertIsNone(score(values))

    def test_grade_and_acceptability_bands(self):
        self.assertEqual([grade(v) for v in (90, 68, 64, 55, 40)], ["A+", "C", "C−", "D", "F"])
        self.assertEqual([acceptability(v) for v in (75, 70, 60, 49.9)], ["qabul qilinadi", "qabul qilinadi", "chegaraviy", "qabul qilinmaydi"])

    def test_summary_statistics(self):
        result = summarize([75.0, 50.0, 100.0])
        self.assertEqual((result["n"], result["mean"], result["sd"], result["median"]), (3, 75.0, 25.0, 75.0))
        # t(0.975; 2) = 4.3027 → 75 ± 4.3027 × 25 / √3 = 75 ± 62.10
        self.assertEqual(result["ci95"], [12.9, 137.1])
        self.assertEqual(result["benchmark"]["t"], 0.485)
        self.assertEqual((result["grade"], result["acceptability"]), ("B", "qabul qilinadi"))


class SusSurveyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user("sus_teacher", role=User.Role.TEACHER)
        cls.group = StudentGroup.objects.create(name="SUS-1")
        cls.other = StudentGroup.objects.create(name="SUS-2")
        call_command("seed_sus", "--author", "sus_teacher", "--group", "SUS-1", stdout=StringIO())
        cls.quiz = Quiz.objects.get(title=SUS_TITLE)

    def answer(self, name, values, group=None):
        student = User.objects.create_user(name, role=User.Role.STUDENT, group=group or self.group)
        questions = {q.order: q for q in self.quiz.questions.prefetch_related("choices")}
        answers = {}
        for order, value in values.items():
            choice = next(c for c in questions[order].choices.all() if c.order == value)
            answers[str(questions[order].pk)] = [choice.pk]
        QuizAttempt.objects.create(quiz=self.quiz, student=student, answers=answers, submitted_at=timezone.now())
        return student

    def test_seed_creates_ten_ordered_likert_items_once(self):
        self.assertEqual(self.quiz.kind, Quiz.Kind.SURVEY)
        questions = list(self.quiz.questions.order_by("order"))
        self.assertEqual([q.order for q in questions], list(range(1, 11)))
        self.assertEqual([q.text for q in questions], SUS_ITEMS)
        self.assertTrue(all(q.kind == "likert" and q.choices.count() == 5 for q in questions))
        call_command("seed_sus", "--author", "sus_teacher", "--group", "SUS-2", stdout=StringIO())
        self.assertEqual(Quiz.objects.filter(title=SUS_TITLE).count(), 1)
        self.assertEqual(set(self.quiz.groups.values_list("name", flat=True)), {"SUS-1", "SUS-2"})

    def test_seed_rejects_unknown_group(self):
        with self.assertRaises(CommandError):
            call_command("seed_sus", "--author", "sus_teacher", "--group", "yoq", stdout=StringIO())

    def test_report_scores_students_and_counts_incomplete(self):
        self.answer("s1", {o: 4 if o % 2 else 2 for o in range(1, 11)})  # 75
        self.answer("s2", {o: 3 for o in range(1, 11)})  # 50
        self.answer("s3", {o: 5 if o % 2 else 1 for o in range(1, 11)})  # 100
        self.answer("s4", {o: 3 for o in range(1, 10)})  # 10-fikr javobsiz
        data = report(self.quiz)
        self.assertEqual((data["submitted"], data["incomplete"]), (4, 1))
        self.assertEqual(sorted(data["scores"].values()), [50.0, 75.0, 100.0])
        self.assertEqual(data["summary"]["mean"], 75.0)
        # Fikrlar statistikasiga to'liqsiz javob berganning javoblari ham kiradi: (4 + 3 + 5 + 3) / 4
        self.assertEqual(data["items"][0]["mean"], 3.75)
        self.assertEqual(data["items"][9]["n"], 3)

    def test_report_command_filters_group(self):
        self.answer("g1", {o: 3 for o in range(1, 11)})
        self.answer("g2", {o: 5 if o % 2 else 1 for o in range(1, 11)}, group=self.other)
        out = StringIO()
        call_command("sus_report", "--quiz", str(self.quiz.pk), "--group", "SUS-1", stdout=out)
        self.assertIn("SUS: M = 50.0", out.getvalue())
        self.assertIn("hisoblandi: 1", out.getvalue())
