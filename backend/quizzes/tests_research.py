"""Test psixometrikasi (KR-20, savollar, variantlar, so'rovnoma α) va tajriba natijasining statistik tahlili.

Kutilgan qiymatlar scipy.stats va numpy (eng kichik kvadratlar) bilan hisoblangan.
"""
import json
from datetime import timedelta

from django.core.cache import cache
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from ai.models import ChatMessage
from competence import stats
from labs.models import AIAction, Lab, LabAttempt
from learning.models import Assignment
from labs.psychometrics import cronbach_alpha
from users.consent import record_decision
from users.models import StudentGroup, User

from .experiment import analyse as analyse_experiment, attrition_stage, compare_independent, hake_level
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

    def test_holm_tost_icc(self):
        # statsmodels.stats.multitest.multipletests(method="holm")
        self.assertEqual([round(p, 10) for p in stats.holm([0.01, 0.04, 0.03, 0.005, None])[:4]], [0.03, 0.06, 0.06, 0.02])
        self.assertIsNone(stats.holm([0.01, None])[1])
        # statsmodels.stats.weightstats.ttost_ind(a, b, -10, 10, usevar="unequal")
        result = stats.tost([60, 72, 65, 80, 75, 68, 71], [55, 58, 62, 50, 66, 59, 61, 57], 10)
        self.assertAlmostEqual(result["p"], 0.7019397109246388, places=9)
        self.assertAlmostEqual(result["p_lower"], 9.319629219148351e-06, places=12)
        self.assertFalse(result["equivalent"])
        self.assertTrue(stats.tost([60, 61, 59, 62, 58], [60.5, 59.5, 61, 60, 59], 5)["equivalent"])
        # ICC(1): F va p — scipy.stats.f_oneway, ICC — ANOVA formulasi (numpy)
        result = stats.icc_oneway([[50, 55, 60, 52], [70, 65, 72, 68, 75], [58, 61, 57]])
        self.assertAlmostEqual(result["icc"], 0.8405056562096863, places=10)
        self.assertAlmostEqual(result["p"], 0.0003643955882313509, places=10)
        self.assertAlmostEqual(result["design_effect"], 1 + 3 * result["icc"], places=10)
        self.assertIsNone(stats.icc_oneway([[1, 2, 3]]))

    def test_confidence_intervals(self):
        # scipy.stats.ttest_ind(...).confidence_interval(0.95)
        student = stats.mean_difference_ci(AI_POST, C_POST, equal_var=True)
        self.assertEqual(student["diff"], 10.75)
        self.assertAlmostEqual(student["ci"][0], -2.469799740665108, places=8)
        self.assertAlmostEqual(student["ci"][1], 23.96979974066511, places=8)
        welch = stats.mean_difference_ci(AI_POST, C_POST, equal_var=False)
        self.assertAlmostEqual(welch["ci"][0], -2.567632584395481, places=8)
        self.assertAlmostEqual(welch["ci"][1], 24.067632584395483, places=8)
        self.assertIsNone(stats.mean_difference_ci([5, 5], [5, 5], equal_var=True))
        self.assertIsNone(stats.mean_difference_ci([5, 5], [5, 5], equal_var=False))
        # Xedjes–Olkin formulasi bo'yicha numpy bilan
        g = stats.hedges_g_ci(AI_POST, C_POST)
        self.assertAlmostEqual(g["value"], 0.8244766335797706, places=10)
        self.assertAlmostEqual(g["ci"][0], -0.1962912639213168, places=10)
        self.assertAlmostEqual(g["ci"][1], 1.845244531080858, places=10)
        self.assertIsNone(stats.hedges_g_ci([5, 5], [5, 5]))

    def test_ancova_adjusted_difference(self):
        # numpy: (XᵀX)⁻¹ dan guruh koeffitsiyenti xatosi, t(13) kvantili
        result = stats.ancova({"e": list(zip(AI_PRE, AI_POST)), "c": list(zip(C_PRE, C_POST))})
        self.assertAlmostEqual(result["adjusted_diff"], 10.503854283227652, places=8)
        self.assertAlmostEqual(result["adjusted_diff_ci"][0], 6.503533257900994, places=8)
        self.assertAlmostEqual(result["adjusted_diff_ci"][1], 14.50417530855431, places=8)
        self.assertAlmostEqual(result["hedges_g"]["value"], 0.8055983645626036, places=8)
        self.assertAlmostEqual(result["hedges_g"]["ci"][0], 0.498791740171934, places=8)
        self.assertAlmostEqual(result["hedges_g"]["ci"][1], 1.1124049889532734, places=8)

    def test_hodges_lehmann(self):
        # Kutilgan chegaralar: scipy.stats.mannwhitneyu(a − δ, b, asymptotic, use_continuity=False) p ≥ 0.05 bo'lgan δ lar
        a, b = [12, 15, 9, 20, 35, 14, 11, 13, 50, 10], [22, 31, 18, 40, 28, 25, 19, 60, 33]
        result = stats.hodges_lehmann(a, b)
        self.assertEqual((result["shift"], result["ci"], result["approximate"]), (-12, (-21, -4), False))
        self.assertEqual(stats.hodges_lehmann([1, 2, 3], [4, 5, 6])["ci"], (-5, -1))
        # Bir xil ballar ko'p: farqlar orasida guruhlararo tenglik yo'q, tuzatma faqat guruh ichidagilardan
        tied = stats.hodges_lehmann([70, 70, 80, 80, 90, 100, 100, 60, 70], [50, 60, 60, 70, 70, 80, 50, 40])
        self.assertEqual((tied["shift"], tied["ci"]), (20, (0, 30)))
        # Juda kichik tanlanma: 95% oraliqqa erishib bo'lmaydi
        self.assertIsNone(stats.hodges_lehmann([1, 2], [3, 4])["ci"])
        self.assertIsNone(stats.hodges_lehmann([], [3, 4]))
        self.assertEqual(stats.hodges_lehmann([5, 5], [5, 5]), {"shift": 0, "ci": None, "approximate": True})

    def test_spearman(self):
        # scipy.stats.spearmanr; oraliq — Fisher z, Bonett–Rayt xatosi (numpy)
        result = stats.spearman([1, 2, 3, 4, 5, 6], [2, 1, 4, 3, 6, 5])
        self.assertAlmostEqual(result["rho"], 0.8285714285714287, places=10)
        self.assertAlmostEqual(result["p"], 0.04156268221574335, places=10)
        tied = stats.spearman([1, 1, 2, 2, 3, 4], [5, 6, 6, 7, 8, 8])
        self.assertAlmostEqual(tied["rho"], 0.909090909090909, places=10)
        self.assertAlmostEqual(tied["p"], 0.012021036814425278, places=10)
        self.assertIsNone(stats.spearman([1, 1, 1], [1, 2, 3]))
        self.assertIsNone(stats.spearman([1, 2], [1, 2]))
        perfect = stats.spearman([1, 2, 3, 4], [2, 4, 6, 8])
        self.assertEqual((perfect["rho"], perfect["ci"]), (1.0, None))
        residuals = stats.linear_residuals(AI_PRE, AI_POST)
        self.assertAlmostEqual(residuals[0], 3.8571428571428754, places=8)
        self.assertAlmostEqual(residuals[6], -7.917293233082688, places=8)
        self.assertEqual(stats.linear_residuals([1, 1, 1], [1, 2, 3]), [-1, 0, 1])

    def test_fisher_exact(self):
        # scipy.stats.fisher_exact (ikki tomonlama)
        for table, expected in (
            ([[6, 8], [1, 8]], 0.1759566318726367),
            ([[3, 17], [9, 11]], 0.08235877701951116),
            ([[12, 5], [2, 10]], 0.007775059838501802),
            ([[1, 9], [11, 3]], 0.0027594561852200836),
        ):
            self.assertAlmostEqual(stats.fisher_exact(table)["p"], expected, places=10)
        self.assertAlmostEqual(stats.fisher_exact([[0, 8], [1, 8]])["p"], 1.0, places=10)
        self.assertIsNone(stats.fisher_exact([[0, 0], [1, 8]]))
        self.assertIsNone(stats.fisher_exact([[3, 0], [1, 0]]))

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
        self.assertEqual((exp["gain"]["excluded_full_pre"], exp["ceiling"]["students"], exp["delayed_missing"]), (0, 0, 8))
        self.assertFalse(exp["ceiling"]["warning"])

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
        self.assertEqual(ancova["adjusted_diff"], 10.5)
        self.assertEqual(ancova["adjusted_diff_ci"], [6.5, 14.5])
        self.assertEqual(ancova["hedges_g"], {"value": 0.806, "ci": [0.5, 1.11]})
        # Oraliq tanlangan mezonga mos: Styudent, p = 0.103 — oraliq 0 ni o'z ichiga oladi
        self.assertEqual(post["estimate"], {"name": "O'rtachalar farqi", "value": 10.75, "ci": [-2.47, 23.97], "approximate": False})
        self.assertEqual(post["hedges_g"], {"value": 0.824, "ci": [-0.2, 1.85]})
        self.assertTrue(ancova["primary"])
        self.assertEqual(result["primary"]["outcome"], "ancova")
        # Ikkilamchi natijalar Xolm bo'yicha tuzatiladi (post va gain: ikkita solishtiruv)
        gain = result["comparisons"]["gain"]
        smaller, larger = sorted([post["p"], gain["p"]])
        expected = min(1, 2 * smaller) if post["p"] == smaller else max(2 * smaller, larger)
        self.assertAlmostEqual(post["p_holm"], expected, places=3)
        self.assertNotIn("p_holm", result["baseline"])
        self.assertTrue(result["power"]["achieved"] < 0.8)
        # Har bir shartda bittadan guruh: guruh effekti AI effektidan ajralmaydi
        self.assertTrue(result["clustering"]["confounded"])
        self.assertIsNone(result["clustering"]["icc"])
        text = " ".join(result["conclusions"])
        self.assertIn("teng bo'lgan", text)
        self.assertIn("Asosiy gipoteza", text)
        self.assertIn("Tuzatilgan farq (tajriba − nazorat): 10.5 ball, 95% CI [6.5; 14.5], Xedjes g = 0.806", text)
        self.assertIn("o'rtachalar farqi = 10.75, 95% CI [-2.47; 23.97]", text)
        self.assertIn("Xolm", text)
        self.assertIn("Dizayn cheklovi", text)
        self.assertIn("quvvat past", text)
        self.assertLess(text.index("Asosiy gipoteza"), text.index("Ikkilamchi"))

    def test_full_pre_and_ceiling(self):
        student = self.make_student("e_full", self.ai_group)
        self.submit(self.pre, student, {}, score=100, max_score=100)
        self.submit(self.post, student, {}, score=100, max_score=100)
        for index in range(2):
            other = self.make_student(f"e_top{index}", self.ai_group)
            self.submit(self.pre, other, {}, score=70, max_score=100)
            self.submit(self.post, other, {}, score=100, max_score=100)
        exp = self.result()["cohorts"]["experimental"]
        self.assertEqual(exp["gain"]["excluded_full_pre"], 1)
        self.assertEqual(exp["gain"]["individual"]["n"], 10)
        self.assertEqual(exp["ceiling"], {"students": 3, "share": round(3 / 11, 3), "warning": True})
        text = " ".join(self.result()["conclusions"])
        self.assertIn("100% olgan 1 ta talaba", text)
        self.assertIn("Shift effekti", text)

    def test_clustering_icc(self):
        """Har bir shartda ikkita guruh: ICC ANCOVA qoldiqlari bo'yicha (statsmodels OLS + ANOVA formulasi)."""
        groups = {}
        for name, ai, members in (("E1", True, (0, 1, 2, 5)), ("C1", False, (0, 2, 4, 6))):
            groups[name] = StudentGroup.objects.create(name=f"E-{name}", ai_enabled=ai)
            groups[name].teachers.add(self.teacher)
            prefix = "ea" if ai else "ec"
            User.objects.filter(username__in=[f"{prefix}{index}" for index in members]).update(group=groups[name])
        for quiz in (self.pre, self.post):
            quiz.groups.add(*groups.values())
        result = analyse_experiment(Quiz.objects.filter(author=self.teacher), [self.ai_group, self.control_group, *groups.values()])
        clustering = result["clustering"]
        self.assertEqual(clustering["groups"], {"experimental": 2, "control": 2})
        self.assertFalse(clustering["confounded"])
        self.assertEqual(clustering["icc"]["value"], round(0.15716794246025922, 3))
        self.assertEqual(clustering["icc"]["design_effect"], round(1.4715038273807777, 2))
        self.assertEqual(clustering["icc"]["effective_n"], round(10.873230298340037, 1))
        self.assertIn("Klasterlash", " ".join(result["conclusions"]))

    def test_external_ai_contamination(self):
        from .serializers import QuizSerializer
        from .survey_bank import EXTERNAL_AI_TEXTS

        survey = Quiz.objects.create(kind=Quiz.Kind.SURVEY, title="Yakuniy", author=self.teacher)
        survey.groups.add(self.ai_group, self.control_group)
        texts = ["Laboratoriya foydali bo'ldi.", "Topshiriqlar tushunarli edi.", *sorted(EXTERNAL_AI_TEXTS)]
        QuizSerializer.write_questions(survey, [{"text": text, "kind": "likert", "points": 0, "choices": [
            {"text": str(value), "is_correct": False} for value in range(1, 6)
        ]} for text in texts])
        questions = list(survey.questions.order_by("order"))
        # ec0-ec2 va ea0 — ko'p foydalangan (o'rtacha 4.5), qolganlar — 1; fikr savoliga hamma 5
        heavy = {"ec0", "ec1", "ec2", "ea0"}
        for student in User.objects.filter(group__in=[self.ai_group, self.control_group]).exclude(username__in=["e_refused", "e_dropped"]):
            values = [5, 4, 5, 4] if student.username in heavy else [5, 4, 1, 1]
            answers = {str(q.pk): [q.choices.get(order=value).pk] for q, value in zip(questions, values)}
            QuizAttempt.objects.create(quiz=survey, student=student, answers=answers, submitted_at=timezone.now())
        result = self.result()
        external = result["external_ai"]
        self.assertEqual(external["answered"], 16)
        self.assertEqual(external["cohorts"]["control"]["heavy"], 3)
        self.assertEqual(external["cohorts"]["experimental"]["heavy"], 1)
        # statsmodels: ols("post ~ C(g) + pre"), anova_lm(typ=2), ko'p foydalanganlarsiz
        sensitivity = external["sensitivity"]
        self.assertEqual(sensitivity["excluded"], 4)
        self.assertAlmostEqual(sensitivity["f"], 18.677, places=3)
        self.assertAlmostEqual(sensitivity["p"], 0.0019, places=4)
        self.assertAlmostEqual(sensitivity["partial_eta2"], 0.675, places=3)
        text = " ".join(result["conclusions"])
        self.assertIn("nazorat guruhida 3 ta talaba", text)
        self.assertIn("Sezgirlik tahlili", text)
        # Tashqi AI savollari so'rovnomaning fikr shkalasiga (α) kirmaydi
        from .psychometrics import analyse_survey

        scale = analyse_survey(survey)["scales"][0]
        self.assertEqual([item["text"] for item in scale["items"]], ["Laboratoriya foydali bo'ldi.", "Topshiriqlar tushunarli edi."])

    def test_attrition(self):
        """Faqat bitta nazorat talabasi tashlab ketgan: kutilgan sonlar kichik — Fisher, farq yo'q."""
        attrition = self.result()["attrition"]
        stage = attrition["post"]
        self.assertEqual(
            [(stage["cohorts"][key]["started"], stage["cohorts"][key]["lost"]) for key in ("experimental", "control")], [(8, 0), (9, 1)]
        )
        self.assertEqual((stage["overall"], stage["level"], stage["differential"]), (round(1 / 17, 3), "o'rta", round(-1 / 9, 3)))
        self.assertEqual((stage["test"]["name"], stage["test"]["p"], stage["test"]["significant"]), ("fisher", 1.0, False))
        self.assertIsNone(stage["baseline"])  # tashlab ketgan bitta — solishtirib bo'lmaydi
        self.assertIsNone(attrition["delayed"])
        self.assertIn("Tashlab ketish (kirish → chiqish)", " ".join(self.result()["conclusions"]))

    def test_differential_attrition(self):
        """Tajriba guruhidan kuchsiz talabalar tashlab ketgan: guruhlar farqi va boshlang'ich farq aniqlanadi."""
        for index, score in enumerate([10, 12, 15, 8, 14, 11, 9, 13, 16, 7]):
            self.submit(self.pre, self.make_student(f"e_left{index}", self.ai_group), {}, score=score, max_score=100)
        delayed = Quiz.objects.create(kind=Quiz.Kind.DELAYED, title="Kechiktirilgan", author=self.teacher)
        delayed.groups.add(self.ai_group, self.control_group)
        for username in ("ea0", "ea1", "ec0"):
            self.submit(delayed, User.objects.get(username=username), {}, score=50, max_score=100)
        result = self.result()
        stage = result["attrition"]["post"]
        self.assertEqual(stage["cohorts"]["experimental"]["lost"], 10)
        self.assertEqual(stage["level"], "yuqori")
        # scipy.stats.fisher_exact([[10, 8], [1, 8]])
        self.assertEqual(stage["test"]["name"], "fisher")
        self.assertAlmostEqual(stage["test"]["p"], 0.04167106730035791, places=4)
        self.assertTrue(stage["test"]["significant"])
        self.assertEqual(stage["baseline"]["test"], "mann_whitney")
        self.assertTrue(stage["baseline"]["significant"])
        later = result["attrition"]["delayed"]
        self.assertEqual([later["cohorts"][key]["lost"] for key in ("experimental", "control")], [6, 7])
        # scipy.stats.fisher_exact([[6, 2], [7, 1]])
        self.assertEqual((later["test"]["name"], later["test"]["p"]), ("fisher", 1.0))
        text = " ".join(result["conclusions"])
        self.assertIn("differensial tashlab ketish", text)
        self.assertIn("Tashlab ketganlar kirish testida", text)
        self.assertIn("Kechiktirilgan testgacha tashlab ketish", text)

    def test_attrition_chi_square(self):
        table = [[12, 28], [3, 37]]
        started = {
            "experimental": [{"pre": 50, **({} if i < 12 else {"post": 60})} for i in range(40)],
            "control": [{"pre": 50, **({} if i < 3 else {"post": 60})} for i in range(40)],
        }
        stage = attrition_stage(started, "post", "pre")
        self.assertEqual([[stage["cohorts"][key]["lost"], stage["cohorts"][key]["started"] - stage["cohorts"][key]["lost"]] for key in ("experimental", "control")], table)
        # scipy.stats.chi2_contingency(table, correction=False)
        self.assertEqual(stage["test"]["name"], "chi2")
        self.assertAlmostEqual(stage["test"]["chi2"], 6.646, places=3)
        self.assertAlmostEqual(stage["test"]["p"], 0.0099, places=4)
        self.assertEqual(stage["differential"], 0.225)

    def test_estimate_matches_selected_test(self):
        # Normal bo'lmagan taqsimot: Mann–Uitni tanlanadi, baho ham parametrsiz va oraliq p ga zid emas
        skewed = compare_independent([12, 15, 9, 20, 35, 14, 11, 13, 50, 10], [22, 31, 18, 40, 28, 25, 19, 60, 33])
        self.assertEqual(skewed["test"], "mann_whitney")
        self.assertEqual(skewed["estimate"]["name"], "Xodjes–Leman siljishi")
        self.assertEqual((skewed["estimate"]["value"], skewed["estimate"]["ci"]), (-12, [-21, -4]))
        self.assertTrue(skewed["significant"])
        self.assertLess(skewed["estimate"]["ci"][1], 0)

    def expose(self):
        """Kirish testi 30 kun oldin, chiqish testi 1 kun oldin topshirilgan; dozalar: [3, 1, 5, 2, 4, 1, 0, 0]."""
        now = timezone.now()
        QuizAttempt.objects.filter(quiz=self.pre).update(submitted_at=now - timedelta(days=30))
        QuizAttempt.objects.filter(quiz=self.post).update(submitted_at=now - timedelta(days=1))
        lab = Lab.objects.create(title="L", description="L", author=self.teacher)
        assignment = Assignment.objects.create(title="A", description="A", author=self.teacher, deadline=now)

        def student(name):
            return User.objects.get(username=name)

        def attempt(name, enabled=True, **fields):
            item = LabAttempt.objects.create(lab=lab, student=student(name), is_correct=False, ai_enabled=enabled, **fields)
            LabAttempt.objects.filter(pk=item.pk).update(created_at=now - timedelta(days=5))

        def action(name, days=5):
            item = AIAction.objects.create(student=student(name), kind=AIAction.Kind.LAB_CHAT)
            AIAction.objects.filter(pk=item.pk).update(created_at=now - timedelta(days=days))

        for name, level in (("ea0", 2), ("ea2", 3), ("ea3", 2)):
            attempt(name, ai_hint_level=level, ai_advice="MAXFIY-MASLAHAT", ai_requested_at=now - timedelta(days=5))
        # Darajalargacha bo'lgan eski maslahat — to'liq (3)
        attempt("ea4", ai_advice="MAXFIY-MASLAHAT", ai_requested_at=now - timedelta(days=5))
        for name in ("ea0", "ea1", "ea2", "ea4", "ea5"):
            action(name)
        ChatMessage.objects.create(assignment=assignment, student=student("ea2"), role=ChatMessage.Role.USER, content="MAXFIY-SAVOL")
        ChatMessage.objects.filter(student=student("ea2")).update(created_at=now - timedelta(days=5))
        # AI javobi murojaat emas
        ChatMessage.objects.create(assignment=assignment, student=student("ea1"), role=ChatMessage.Role.ASSISTANT, content="MAXFIY-JAVOB")
        # Oynadan tashqari: kirish testidan oldin va chiqish testidan keyin
        action("ea6", days=40)
        action("ea6", days=0)
        # Rozi bo'lmagan talaba hisobga kirmaydi
        action("e_refused")
        # Nazorat: AI ga kirgan va urinishida AI yoqilgan deb yozilgan talabalar
        action("ec0")
        attempt("ec1", enabled=True)
        attempt("ec2", enabled=False)

    def test_fidelity(self):
        self.expose()
        result = self.result()
        fidelity = result["fidelity"]
        exp, ctrl = fidelity["cohorts"]["experimental"], fidelity["cohorts"]["control"]
        self.assertEqual((exp["students"], exp["users"], exp["uptake"], exp["no_window"]), (8, 6, 0.75, 0))
        self.assertEqual(exp["dose"]["median"], 1.5)
        self.assertEqual(exp["sources"], {"hints": 10, "actions": 5, "chat": 1})
        self.assertEqual((exp["changed_condition"], ctrl["users"], ctrl["changed_condition"]), (0, 1, 1))
        # scipy.stats.spearmanr, kirish testi ta'siri olib tashlangan chiqish natijasi bilan
        self.assertEqual(fidelity["dose_response"], {"n": 8, "rho": 0.253, "ci": [-0.559, 0.817], "p": 0.5454, "significant": False})
        # numpy: foydalanmagan 2 ta (tajriba) va AI ga kirgan 1 ta (nazorat) chiqarilgan
        protocol = fidelity["per_protocol"]
        self.assertEqual((protocol["excluded"], protocol["f"], protocol["df2"]), (3, 41.989, 10))
        self.assertEqual((protocol["adjusted_diff"], protocol["adjusted_diff_ci"]), (11.06, [7.26, 14.87]))
        text = " ".join(result["conclusions"])
        self.assertIn("8 ta talabadan 6 tasi (75%)", text)
        self.assertIn("80% dan kam", text)
        self.assertIn("nazorat guruhida 1 ta talaba", text)
        self.assertIn("1 ta talabaning urinishlarida", text)
        self.assertIn("kuzatuv natijasi, sabab emas", text)
        self.assertIn("per-protocol", text)
        self.assertLess(text.index("Asosiy gipoteza"), text.index("Aralashuvning bajarilishi"))

    def test_fidelity_high_uptake_and_no_usage(self):
        result = self.result()
        fidelity = result["fidelity"]
        self.assertEqual(fidelity["cohorts"]["experimental"]["uptake"], 0)
        self.assertIsNone(fidelity["dose_response"])  # hamma doza 0 — korrelyatsiya yo'q
        self.assertIsNone(fidelity["per_protocol"])  # tajribada foydalanganlar qolmadi
        self.assertIn("80% dan kam", " ".join(result["conclusions"]))
        self.expose()
        for name in ("ea6", "ea7"):
            AIAction.objects.create(student=User.objects.get(username=name), kind=AIAction.Kind.VIVA)
        QuizAttempt.objects.filter(quiz=self.post).update(submitted_at=timezone.now() + timedelta(days=1))
        text = " ".join(self.result()["conclusions"])
        self.assertIn("8 ta talabadan 8 tasi (100%)", text)
        self.assertNotIn("80% dan kam", text)

    def test_fidelity_exposes_no_text_and_respects_scope(self):
        self.expose()
        self.client.force_authenticate(self.teacher)
        response = self.client.get("/api/experiment/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("MAXFIY", json.dumps(response.data, default=str))
        self.client.force_authenticate(User.objects.get(username="ea0"))
        self.assertEqual(self.client.get("/api/experiment/").status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(User.objects.create_user("f_other", role=User.Role.TEACHER))
        fidelity = self.client.get("/api/experiment/").data["fidelity"]
        self.assertEqual(fidelity["cohorts"]["experimental"]["students"], 0)
        self.assertEqual(fidelity["cohorts"]["experimental"]["sources"], {"hints": 0, "actions": 0, "chat": 0})

    def test_fidelity_post_before_pre_has_no_window(self):
        now = timezone.now()
        student = User.objects.get(username="ea0")
        QuizAttempt.objects.filter(quiz=self.pre, student=student).update(submitted_at=now)
        QuizAttempt.objects.filter(quiz=self.post, student=student).update(submitted_at=now - timedelta(days=1))
        exp = self.result()["fidelity"]["cohorts"]["experimental"]
        self.assertEqual((exp["students"], exp["no_window"]), (7, 1))

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


class ParallelFormsTests(ResearchBase):
    """Kutilgan qiymatlar: statsmodels ttost_ind(usevar="unequal"), scipy pearsonr."""

    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user("pf_teacher", role=User.Role.TEACHER)
        cls.groups = [StudentGroup.objects.create(name=f"PF-{index}", ai_enabled=index != 1) for index in range(3)]
        for group in cls.groups:
            group.teachers.add(cls.teacher)
        cls.quizzes = {}
        for kind in (Quiz.Kind.PRE, Quiz.Kind.POST):
            for form in ("A", "B"):
                quiz = Quiz.objects.create(kind=kind, form=form, title=f"{kind}-{form}", author=cls.teacher)
                quiz.groups.add(*cls.groups)
                for order in range(1, 5):
                    question = Question.objects.create(quiz=quiz, order=order, text=f"{form}{order}", kind=Question.Kind.SINGLE, points=1)
                    for index in range(3):
                        Choice.objects.create(question=question, order=index, text=f"V{index}", is_correct=index == 0)
                cls.quizzes[kind, form] = quiz
        pre_a = [[1, 0, 0, 0], [1, 1, 0, 0], [1, 0, 1, 0], [1, 1, 1, 0], [1, 1, 0, 1], [1, 1, 1, 1]]
        pre_b = [[0, 1, 0, 0], [0, 1, 1, 0], [0, 1, 1, 1], [0, 1, 0, 1], [0, 1, 1, 1], [0, 0, 0, 0]]
        pilot = [([1, 1, 0, 0], [0, 1, 1, 0]), ([1, 1, 1, 0], [0, 1, 1, 1]), ([1, 0, 0, 0], [0, 0, 0, 0])]
        for index, pattern in enumerate(pre_a):
            student = cls.make_student(f"pf_a{index}", cls.groups[0])
            cls.answer(("pre", "A"), student, pattern)
            # Birinchi talaba chiqishda ham A variantni olgan — test qilish effekti xavfi
            cls.answer(("post", "A" if index == 0 else "B"), student, [1, 1, 1, 1])
        for index, pattern in enumerate(pre_b):
            cls.answer(("pre", "B"), cls.make_student(f"pf_b{index}", cls.groups[1]), pattern)
        for index, (a, b) in enumerate(pilot):
            student = cls.make_student(f"pf_p{index}", cls.groups[2])
            cls.answer(("pre", "A"), student, a)
            cls.answer(("pre", "B"), student, b)

    @classmethod
    def answer(cls, key, student, pattern):
        quiz = cls.quizzes[key]
        answers = {}
        for question, correct in zip(quiz.questions.order_by("order"), pattern):
            choice = question.choices.get(is_correct=True) if correct else question.choices.filter(is_correct=False).first()
            answers[str(question.pk)] = [choice.pk]
        cls.submit(quiz, student, answers)

    def test_equivalence_reliability_items(self):
        result = analyse_experiment(Quiz.objects.filter(author=self.teacher), self.groups)["forms"]
        pre = next(row for row in result["by_kind"] if row["kind"] == "pre")
        self.assertEqual(pre["A"], {"n": 9, "mean": 58.33, "sd": 25.0})
        self.assertEqual(pre["B"], {"n": 9, "mean": 44.44, "sd": 30.05})
        self.assertAlmostEqual(pre["equivalence"]["p"], 0.6153, places=4)
        self.assertFalse(pre["equivalence"]["equivalent"])
        self.assertEqual(pre["equivalence"]["diff"], 13.89)
        post = next(row for row in result["by_kind"] if row["kind"] == "post")
        self.assertIsNone(post["equivalence"])
        self.assertEqual(result["reliability"]["n"], 3)
        self.assertEqual(result["reliability"]["r"], 0.982)
        first = result["items"][0]
        self.assertEqual((first["order"], first["A"], first["B"], first["gap"]), (1, 1.0, 0.0, True))
        self.assertEqual(result["same_form"], 1)
        self.assertEqual(result["without_form"], 0)
        text = " ".join(analyse_experiment(Quiz.objects.filter(author=self.teacher), self.groups)["conclusions"])
        self.assertIn("ekvivalentligi isbotlanmadi", text)
        self.assertIn("juft savollar: 1", text)
        self.assertIn("Test qilish effekti xavfi: 1 ta", text)
