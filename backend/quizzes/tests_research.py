"""Test psixometrikasi (KR-20, savollar, variantlar, so'rovnoma α) va tajriba natijasining statistik tahlili.

Kutilgan qiymatlar scipy.stats va numpy (eng kichik kvadratlar) bilan hisoblangan.
"""
from django.core.cache import cache
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from competence import stats
from labs.psychometrics import cronbach_alpha
from users.consent import record_decision
from users.models import StudentGroup, User

from .experiment import analyse as analyse_experiment, compare_independent, hake_level
from .models import LIKERT_SCALE, Choice, Question, Quiz, QuizAttempt
from .psychometrics import analyse_quiz


class StatsReferenceTests(SimpleTestCase):
    def test_shapiro_wilk(self):
        result = stats.shapiro_wilk([12, 15, 9, 20, 35, 14, 11, 13, 50, 10])
        self.assertAlmostEqual(result["w"], 0.7311534283819704, places=10)
        self.assertAlmostEqual(result["p"], 0.0021044599964030373, places=10)
        result = stats.shapiro_wilk([55, 61, 58, 62, 57, 60, 59, 63])
        self.assertAlmostEqual(result["p"], 0.9782133904150503, places=10)
        self.assertIsNone(stats.shapiro_wilk([1, 2]))
        self.assertIsNone(stats.shapiro_wilk([5, 5, 5, 5]))

    def test_levene_student_wilcoxon_f(self):
        a, b = [60, 72, 65, 80, 75, 68, 71], [55, 58, 62, 50, 66, 59, 61, 57]
        result = stats.levene(a, b)
        self.assertAlmostEqual(result["f"], 0.5488888888888885, places=10)
        self.assertAlmostEqual(result["p"], 0.4719430517619029, places=10)
        result = stats.student_t_test(a, b)
        self.assertAlmostEqual(result["t"], 3.9537779733443323, places=10)
        self.assertAlmostEqual(result["p"], 0.0016497357900425993, places=10)
        self.assertEqual(result["df"], 13)
        result = stats.wilcoxon_signed_rank([30, 45, 50, 20, 60, 35, 40, 55], [50, 60, 72, 35, 70, 52, 48, 75])
        self.assertAlmostEqual(result["p"], 0.01151382807684542, places=10)
        self.assertAlmostEqual(stats.f_sf(4.2, 1, 17), 0.05618062316763938, places=10)

    def test_normal_ppf_and_power(self):
        self.assertAlmostEqual(stats.normal_ppf(0.975), 1.959963984540054, places=9)
        self.assertAlmostEqual(stats.normal_ppf(0.001), -3.090232306167813, places=9)
        # G*Power: d = 0.5 → 64, d = 0.8 → 26 talaba har bir guruhda (α = 0.05, quvvat 0.8)
        self.assertEqual(stats.required_n_per_group(0.5), 64)
        self.assertEqual(stats.required_n_per_group(0.8), 26)
        self.assertAlmostEqual(stats.achieved_power(0.5, 64, 64), 0.8, delta=0.02)

    def test_hake_levels(self):
        self.assertEqual([hake_level(g) for g in (0.1, 0.3, 0.69, 0.7)], ["past", "o'rta", "o'rta", "yuqori"])

    def test_test_selection(self):
        normal = compare_independent([55, 61, 58, 62, 57, 60, 59, 63], [50, 54, 52, 57, 53, 55, 51, 56])
        self.assertEqual(normal["test"], "student")
        skewed = compare_independent([12, 15, 9, 20, 35, 14, 11, 13, 50, 10], [55, 61, 58, 62, 57, 60, 59, 63])
        self.assertEqual(skewed["test"], "mann_whitney")
        self.assertEqual(skewed["effect"]["name"], "r")
        unequal = compare_independent([50, 50.5, 51, 49.5, 50.2, 49.8, 50.1, 49.9], [20, 80, 35, 65, 50, 45, 55, 30])
        self.assertEqual(unequal["test"], "welch")
        self.assertIsNone(compare_independent([1, 2], [3, 4, 5]))


class ResearchBase(APITestCase):
    @classmethod
    def make_student(cls, name, group, consent=True):
        student = User.objects.create_user(name, role=User.Role.STUDENT, group=group)
        if consent is not None:
            record_decision(student, consent)
        return student

    @staticmethod
    def submit(quiz, student, answers, score=None, max_score=None):
        results = {}
        if score is None:
            for question in quiz.questions.prefetch_related("choices"):
                correct = {choice.pk for choice in question.choices.all() if choice.is_correct}
                results[str(question.pk)] = float(question.points) if set(answers.get(str(question.pk), [])) == correct else 0.0
            score, max_score = sum(results.values()), sum(q.points for q in quiz.questions.all())
        return QuizAttempt.objects.create(
            quiz=quiz, student=student, answers=answers, results=results, score=score, max_score=max_score, submitted_at=timezone.now()
        )

    def setUp(self):
        cache.clear()


class QuizPsychometricsTests(ResearchBase):
    @classmethod
    def setUpTestData(cls):
        cls.group = StudentGroup.objects.create(name="QP-guruh")
        cls.teacher = User.objects.create_user("qp_teacher", role=User.Role.TEACHER)
        cls.group.teachers.add(cls.teacher)
        cls.quiz = Quiz.objects.create(kind=Quiz.Kind.PRE, title="Kirish", author=cls.teacher)
        cls.quiz.groups.add(cls.group)
        cls.questions = []
        for order in range(1, 6):
            question = Question.objects.create(quiz=cls.quiz, order=order, text=f"Savol {order}", kind=Question.Kind.SINGLE, points=1)
            choices = [Choice.objects.create(question=question, order=i, text=f"V{i}", is_correct=i == 0) for i in range(4)]
            cls.questions.append((question, choices))
        # 8 talaba, kuchlidan kuchsizga. Har bir talaba uchun savollarga tanlagan variant raqami (0 — to'g'ri)
        pattern = [
            [0, 0, 0, 0, 1],
            [0, 0, 0, 0, 1],
            [0, 0, 0, 1, 1],
            [0, 0, 1, 0, 1],
            [0, 1, 0, 1, 0],
            [0, 1, 1, 1, 0],
            [0, 2, 1, 1, 0],
            [0, 1, 2, 1, 0],
        ] * 2
        # V3 hech qachon tanlanmaydi (ishlamaydigan distraktor); 5-savol teskari ajratadi.
        # 16 talaba: yuqori va quyi 27% guruhlarda 4 tadan
        cls.students = [cls.make_student(f"qp_s{index}", cls.group) for index in range(len(pattern))]
        for student, row in zip(cls.students, pattern):
            answers = {str(question.pk): [choices[pick].pk] for (question, choices), pick in zip(cls.questions, row)}
            cls.submit(cls.quiz, student, answers)
        refused = cls.make_student("qp_refused", cls.group, consent=False)
        cls.submit(cls.quiz, refused, {})
        cls.matrix = [[1.0 if pick == 0 else 0.0 for pick in row] for row in pattern]

    def test_reliability_and_items(self):
        result = analyse_quiz(self.quiz)
        self.assertTrue(result["enough"])
        self.assertEqual((result["students"], result["excluded_no_consent"]), (16, 1))
        self.assertEqual(result["extreme_groups"], 4)
        reliability = result["reliability"]
        self.assertEqual(reliability["coefficient"], "KR-20")
        alpha = cronbach_alpha(self.matrix)
        self.assertEqual(reliability["alpha"], round(alpha, 3))
        rows = {row["order"]: row for row in result["questions"]}
        self.assertEqual(rows[1]["p"], 1.0)  # hamma to'g'ri: juda oson, r hisoblanmaydi
        self.assertIsNone(rows[1]["r"])
        self.assertIn("Juda oson", rows[1]["advice"][0])
        self.assertEqual(rows[2]["p"], 0.5)
        self.assertGreater(rows[2]["r"], 0.2)
        self.assertEqual(rows[2]["d"], 1.0)
        self.assertLess(rows[5]["r"], 0)
        self.assertEqual(rows[5]["verdict"]["key"], "replace")
        # 4-variant (V3) hech kim tanlamagan
        dead = next(choice for choice in rows[2]["choices"] if choice["text"] == "V3")
        self.assertEqual(dead["share"], 0.0)
        self.assertIn("Deyarli hech kim", dead["flag"])
        # 5-savolda kuchli talabalar to'g'ri javobni kamroq tanlagan
        key = next(choice for choice in rows[5]["choices"] if choice["is_correct"])
        self.assertIn("kalitni tekshiring", key["flag"])

    def test_not_enough_students(self):
        quiz = Quiz.objects.create(kind=Quiz.Kind.POST, title="Bo'sh", author=self.teacher)
        Question.objects.create(quiz=quiz, order=1, text="a", points=1)
        Question.objects.create(quiz=quiz, order=2, text="b", points=1)
        self.assertFalse(analyse_quiz(quiz)["enough"])

    def test_survey_scales(self):
        survey = Quiz.objects.create(kind=Quiz.Kind.SURVEY, title="So'rovnoma", author=self.teacher)
        items = []
        for order in range(1, 5):
            question = Question.objects.create(quiz=survey, order=order, text=f"Fikr {order}", kind=Question.Kind.LIKERT, points=0)
            choices = [Choice.objects.create(question=question, order=value, text=text) for value, text in enumerate(LIKERT_SCALE, start=1)]
            items.append((question, choices))
        values = [[5, 5, 4, 1], [4, 4, 4, 2], [4, 5, 5, 1], [2, 2, 1, 4], [3, 3, 2, 3], [1, 2, 1, 5]]
        for student, row in zip(self.students, values):
            # 4-fikrga oxirgi talaba javob bermagan
            answers = {str(q.pk): [choices[value - 1].pk] for (q, choices), value in zip(items, row)}
            self.submit(survey, student, answers, score=0, max_score=0)
        result = analyse_quiz(survey)
        self.assertEqual(result["kind"], "survey")
        scale = result["scales"][0]
        matrix = values
        self.assertEqual(scale["alpha"], round(cronbach_alpha(matrix), 3))
        reverse = next(item for item in scale["items"] if item["order"] == 4)
        self.assertLess(reverse["r"], 0)
        self.assertIn("teskari", reverse["advice"][0])

    def test_api(self):
        url = f"/api/quizzes/{self.quiz.pk}/analysis/"
        self.client.force_authenticate(self.students[0])
        self.assertEqual(self.client.get(url).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.teacher)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["questions"]), 5)
        other = User.objects.create_user("qp_other", role=User.Role.TEACHER)
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)


AI_PRE, AI_POST = [30, 45, 50, 20, 60, 35, 40, 55], [50, 60, 72, 35, 70, 52, 48, 75]
C_PRE, C_POST = [32, 40, 48, 25, 58, 38, 42, 50], [38, 46, 55, 30, 62, 42, 47, 56]


class ExperimentTests(ResearchBase):
    @classmethod
    def setUpTestData(cls):
        cls.ai_group = StudentGroup.objects.create(name="E-tajriba", ai_enabled=True)
        cls.control_group = StudentGroup.objects.create(name="E-nazorat", ai_enabled=False)
        cls.teacher = User.objects.create_user("e_teacher", role=User.Role.TEACHER)
        for group in (cls.ai_group, cls.control_group):
            group.teachers.add(cls.teacher)
        cls.pre = Quiz.objects.create(kind=Quiz.Kind.PRE, title="Kirish", author=cls.teacher)
        cls.post = Quiz.objects.create(kind=Quiz.Kind.POST, title="Chiqish", author=cls.teacher)
        for quiz in (cls.pre, cls.post):
            quiz.groups.add(cls.ai_group, cls.control_group)
        for prefix, group, pres, posts in (("ea", cls.ai_group, AI_PRE, AI_POST), ("ec", cls.control_group, C_PRE, C_POST)):
            for index, (pre, post) in enumerate(zip(pres, posts)):
                student = cls.make_student(f"{prefix}{index}", group)
                cls.submit(cls.pre, student, {}, score=pre, max_score=100)
                cls.submit(cls.post, student, {}, score=post, max_score=100)
        # Rozi bo'lmagan talaba juda yuqori natija bilan — tahlilga kirmasligi kerak
        refused = cls.make_student("e_refused", cls.ai_group, consent=False)
        cls.submit(cls.pre, refused, {}, score=0, max_score=100)
        cls.submit(cls.post, refused, {}, score=100, max_score=100)
        # Faqat kirish testini topshirgan (tajribadan chiqib ketgan)
        dropped = cls.make_student("e_dropped", cls.control_group)
        cls.submit(cls.pre, dropped, {}, score=40, max_score=100)

    def result(self):
        return analyse_experiment(Quiz.objects.filter(author=self.teacher), [self.ai_group, self.control_group])

    def test_descriptives_and_gain(self):
        result = self.result()
        self.assertEqual(result["excluded_no_consent"], 1)
        exp, ctrl = result["cohorts"]["experimental"], result["cohorts"]["control"]
        self.assertEqual((exp["students"], ctrl["students"], ctrl["dropped"]), (8, 8, 1))
        self.assertEqual(exp["pre"]["mean"], 41.88)
        self.assertEqual(exp["gain"]["class"], round(0.2731182795698925, 3))
        self.assertEqual(exp["gain"]["level"], "past")
        self.assertEqual(ctrl["gain"]["class"], round(0.09207708779443255, 3))
        self.assertEqual(exp["pre_post"]["test"], "paired_t")
        self.assertAlmostEqual(exp["pre_post"]["statistic"]["value"], 9.088, places=3)

    def test_baseline_comparison_and_ancova(self):
        result = self.result()
        baseline = result["baseline"]
        self.assertEqual(baseline["test"], "student")
        self.assertFalse(baseline["significant"])
        self.assertAlmostEqual(baseline["p"], 0.9673, places=4)
        post = result["comparisons"]["post"]
        self.assertEqual(post["test"], "student")
        self.assertAlmostEqual(post["p"], 0.103, places=3)
        self.assertFalse(post["significant"])
        ancova = result["ancova"]
        self.assertAlmostEqual(ancova["f"], 32.178, places=3)
        self.assertTrue(ancova["significant"])
        self.assertAlmostEqual(ancova["partial_eta2"], 0.712, places=3)
        self.assertEqual(ancova["adjusted_means"], {"experimental": 57.63, "control": 47.12})
        self.assertEqual(ancova["effect_label"], "katta")
        self.assertTrue(result["power"]["achieved"] < 0.8)
        text = " ".join(result["conclusions"])
        self.assertIn("teng bo'lgan", text)
        self.assertIn("ANCOVA", text)
        self.assertIn("quvvat past", text)

    def test_too_few_students(self):
        result = analyse_experiment(Quiz.objects.filter(author=self.teacher), [self.ai_group])
        self.assertIsNone(result["baseline"])
        self.assertIsNone(result["ancova"])
        self.assertIn("kamida 3", result["conclusions"][0])

    def test_api(self):
        self.client.force_authenticate(User.objects.get(username="ea0"))
        self.assertEqual(self.client.get("/api/experiment/").status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.teacher)
        response = self.client.get("/api/experiment/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["quizzes"], {"pre": 1, "post": 1, "delayed": 0})
        # Boshqa o'qituvchi bu testlar va guruhlarni ko'rmaydi
        self.client.force_authenticate(User.objects.create_user("e_other", role=User.Role.TEACHER))
        self.assertEqual(self.client.get("/api/experiment/").data["cohorts"]["experimental"]["students"], 0)
