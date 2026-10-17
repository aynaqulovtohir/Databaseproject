"""Kompetentlik modeli: ko'rsatkichlar hisobi, darajalar, kesimlar va kirish huquqlari."""
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from labs.models import LabAttempt
from labs.tests import BaseTestCase
from quizzes.models import Choice, Question, Quiz, QuizAttempt
from users.models import User

from . import stats
from .models import Component, Indicator
from .services import level

REPORT = "/api/competence/report/"


class LevelTests(SimpleTestCase):
    def test_boundaries(self):
        self.assertEqual(level(39.9, 40, 70), "low")
        self.assertEqual(level(40, 40, 70), "medium")
        self.assertEqual(level(70, 40, 70), "high")
        self.assertIsNone(level(None, 40, 70))


class CompetenceTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.component = Component.objects.create(name="Kognitiv", order=1, medium_from=40, high_from=70)
        cls.pre = cls.make_quiz(Quiz.Kind.PRE, "Kirish")
        cls.post = cls.make_quiz(Quiz.Kind.POST, "Chiqish")
        cls.quiz_indicator = Indicator.objects.create(component=cls.component, name="Test", source=Indicator.Source.QUIZ)
        cls.quiz_indicator.initial_quizzes.add(cls.pre)
        cls.quiz_indicator.final_quizzes.add(cls.post)

    @classmethod
    def make_quiz(cls, kind, title, likert=()):
        quiz = Quiz.objects.create(kind=kind, title=title, author=cls.teacher_a)
        quiz.groups.add(cls.group_a, cls.group_b)
        for order, text in enumerate(likert, start=1):
            question = Question.objects.create(quiz=quiz, order=order, text=text, kind=Question.Kind.LIKERT, points=0)
            for value in range(1, 6):
                Choice.objects.create(question=question, order=value, text=str(value))
        return quiz

    def submit(self, quiz, student, score, max_score=10, answers=None):
        return QuizAttempt.objects.create(
            quiz=quiz, student=student, score=score, max_score=max_score, answers=answers or {}, submitted_at=timezone.now()
        )

    def likert_answers(self, quiz, values):
        """values — {savol matni: 1-5}."""
        answers = {}
        for question in quiz.questions.all():
            if question.text in values:
                answers[str(question.pk)] = [question.choices.get(order=values[question.text]).pk]
        return answers

    def report(self, stage, group=None, user=None):
        self.auth_as(user or self.teacher_a)
        response = self.client.get(REPORT, {"group": (group or self.group_a).pk, "stage": stage})
        self.assertEqual(response.status_code, 200, response.data)
        return {row["id"]: row for row in response.data["students"]}, response.data["summary"]

    def score(self, rows, student, component=None):
        return rows[student.pk]["components"][str((component or self.component).pk)]

    def test_quiz_indicator_uses_the_stage_quiz(self):
        self.submit(self.pre, self.student_a1, 3)  # 30% — past
        self.submit(self.post, self.student_a1, 8)  # 80% — yuqori
        initial, _ = self.report("initial")
        final, summary = self.report("final")
        self.assertEqual(self.score(initial, self.student_a1), {"score": 30.0, "level": "low"})
        self.assertEqual(self.score(final, self.student_a1), {"score": 80.0, "level": "high"})
        # Topshirmagan talaba past daraja emas, o'lchanmagan
        self.assertEqual(self.score(final, self.student_a2), {"score": None, "level": None})
        distribution = summary["components"][0]["distribution"]
        self.assertEqual(distribution["counts"], {"low": 0, "medium": 0, "high": 1})
        self.assertEqual((distribution["measured"], distribution["unmeasured"]), (1, 1))

    def test_unsubmitted_attempt_is_not_counted(self):
        QuizAttempt.objects.create(quiz=self.pre, student=self.student_a1, score=9, max_score=10)
        initial, _ = self.report("initial")
        self.assertIsNone(self.score(initial, self.student_a1)["score"])

    def test_weighted_mean_of_indicators(self):
        labs = Indicator.objects.create(component=self.component, name="Lab", source=Indicator.Source.LABS, weight=3)
        self.submit(self.post, self.student_a1, 2)  # 20%
        LabAttempt.objects.create(lab=self.lab, student=self.student_a1, sql_code="SELECT 1", is_correct=True)
        final, _ = self.report("final")
        # (1 * 20 + 3 * 100) / 4 = 80
        self.assertEqual(self.score(final, self.student_a1)["score"], 80.0)
        # Laboratoriyalar o'quv jarayonida yig'iladi: tajriba boshida o'lchanmaydi
        self.submit(self.pre, self.student_a1, 2)
        initial, _ = self.report("initial")
        self.assertEqual(self.score(initial, self.student_a1)["score"], 20.0)
        labs.delete()

    def test_labs_indicator_filters_topics(self):
        Indicator.objects.create(component=self.component, name="ER", source=Indicator.Source.LABS, topics=["er"])
        LabAttempt.objects.create(lab=self.lab, student=self.student_a1, sql_code="SELECT 1", is_correct=True)
        final, _ = self.report("final")
        # Guruhda ER laboratoriyasi yo'q (cls.lab — SELECT): ko'rsatkich o'lchanmaydi
        self.assertIsNone(self.score(final, self.student_a1)["score"])

    def test_survey_counts_only_statements_common_to_all_linked_surveys(self):
        motivation = Component.objects.create(name="Motivatsion", order=2)
        experimental = self.make_quiz(Quiz.Kind.SURVEY, "TG", likert=["Umumiy fikr", "AI haqida"])
        control = self.make_quiz(Quiz.Kind.SURVEY, "NG", likert=["Umumiy fikr"])
        survey = Indicator.objects.create(component=motivation, name="So'rovnoma", source=Indicator.Source.SURVEY)
        survey.final_quizzes.add(experimental, control)
        self.submit(experimental, self.student_a1, 0, 0, self.likert_answers(experimental, {"Umumiy fikr": 4, "AI haqida": 1}))
        final, _ = self.report("final")
        # Faqat umumiy fikr: 4 → (4 - 1) / 4 = 75%; "AI haqida" (1) hisobga olinmaydi
        self.assertEqual(self.score(final, self.student_a1, motivation)["score"], 75.0)

    def test_explanation_is_not_measured_without_ai(self):
        reflective = Component.objects.create(name="Refleksiv", order=3)
        Indicator.objects.create(component=reflective, name="Tushuntirish", source=Indicator.Source.EXPLANATION)
        for student in (self.student_a1, self.student_b):
            self.lab.groups.add(student.group)
            LabAttempt.objects.create(
                lab=self.lab, student=student, sql_code="SELECT 1", is_correct=True, explanation_verdict="partial"
            )
        final_a, _ = self.report("final")
        self.assertEqual(self.score(final_a, self.student_a1, reflective)["score"], 50.0)
        self.group_b.ai_enabled = False
        self.group_b.save()
        final_b, _ = self.report("final", group=self.group_b, user=self.admin)
        self.assertIsNone(self.score(final_b, self.student_b, reflective)["score"])

    def test_interview_coverage_indicator(self):
        from labs.interview_labs import INTERVIEW_LABS
        from labs.models import InterviewMessage, Lab

        component = Component.objects.create(name="Faoliyatli", order=4)
        Indicator.objects.create(component=component, name="Talablar", source=Indicator.Source.INTERVIEW)
        lab = Lab.objects.create(**INTERVIEW_LABS[0], author=self.teacher_a)
        lab.groups.add(self.group_a)
        InterviewMessage.objects.create(lab=lab, student=self.student_a1, role="assistant", content="x", revealed=["R1", "R2", "R3"])
        final, _ = self.report("final")
        self.assertEqual(self.score(final, self.student_a1, component)["score"], 25.0)  # 3 / 12
        # Suhbatni boshlamagan talaba — o'lchanmagan (nol emas)
        self.assertIsNone(self.score(final, self.student_a2, component)["score"])

    @override_settings(RESEARCH_CONSENT_REQUIRED=False)  # bu test eksport mazmunini tekshiradi, rozilik — users/tests_consent.py

    def test_comparison_splits_experimental_and_control(self):
        self.group_b.ai_enabled = False
        self.group_b.save()
        self.submit(self.post, self.student_a1, 9)
        self.submit(self.post, self.student_b, 5)
        self.auth_as(self.admin)
        data = self.client.get("/api/competence/comparison/").data
        cohorts = data["cohorts"]
        self.assertEqual((cohorts["experimental"]["students"], cohorts["control"]["students"]), (2, 1))
        final = {name: cohorts[name]["stages"]["final"]["components"][0] for name in cohorts}
        self.assertEqual(final["experimental"]["distribution"]["counts"]["high"], 1)
        self.assertEqual(final["control"]["distribution"]["counts"]["medium"], 1)

    def test_access(self):
        self.auth_as(self.student_a1)
        for url in ("/api/competence/model/", "/api/competence/comparison/", f"{REPORT}?group={self.group_a.pk}"):
            self.assertEqual(self.client.get(url).status_code, 403, url)
        # O'qituvchi faqat o'zi o'qitadigan guruhlarni ko'radi
        self.auth_as(self.teacher_b)
        self.assertEqual(self.client.get(REPORT, {"group": self.group_a.pk}).status_code, 404)
        groups = self.client.get("/api/competence/comparison/").data["groups"]
        self.assertEqual([row["id"] for row in groups], [self.group_b.pk])
        self.assertEqual(self.client.get(REPORT, {"group": self.group_b.pk, "stage": "boshqa"}).status_code, 400)
        self.assertEqual(self.client.get(REPORT, {"group": "x"}).status_code, 400)

    @override_settings(RESEARCH_CONSENT_REQUIRED=False)  # bu test eksport mazmunini tekshiradi, rozilik — users/tests_consent.py

    def test_research_export_has_anonymous_competence_rows(self):
        import csv
        import io
        import zipfile

        self.submit(self.pre, self.student_a1, 3)
        self.auth_as(self.teacher_a)
        response = self.client.get("/api/labs/research-export/")
        self.assertEqual(response.status_code, 200)
        content = zipfile.ZipFile(io.BytesIO(response.content)).read("kompetentlik.csv").decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(content), delimiter=";"))
        # O'qituvchi faqat o'z guruhi talabalarini oladi: 2 talaba × 3 kesim × (1 komponent + umumiy)
        self.assertEqual(len(rows), 12)
        self.assertEqual({row["guruh"] for row in rows}, {self.group_a.name})
        initial = [row for row in rows if row["kesim"] == "boshida" and row["komponent"] == "Kognitiv" and row["ball"]]
        self.assertEqual([(row["ball"], row["daraja"]) for row in initial], [("30.0", "past")])
        for student in (self.student_a1, self.student_a2):
            self.assertNotIn(student.username, content)
        self.assertNotIn("Zuhriddin", content)

    def test_model_payload_lists_stages(self):
        Indicator.objects.create(component=self.component, name="Lab", source=Indicator.Source.LABS)
        self.auth_as(self.teacher_a)
        component = self.client.get("/api/competence/model/").data["components"][0]
        self.assertEqual(component["stages"], ["initial", "final"])
        self.assertEqual([item["stages"] for item in component["indicators"]], [["initial", "final"], ["final"]])


class SeedCommandTests(BaseTestCase):
    def test_seed_creates_model_and_links_quizzes(self):
        pre = Quiz.objects.create(kind=Quiz.Kind.PRE, title="Kirish", author=self.teacher_a)
        call_command("seed_competence_model", stdout=StringIO())
        self.assertEqual(Component.objects.count(), 5)
        quiz_indicator = Indicator.objects.get(source=Indicator.Source.QUIZ)
        self.assertEqual(list(quiz_indicator.initial_quizzes.all()), [pre])
        with self.assertRaises(CommandError):
            call_command("seed_competence_model", stdout=StringIO())
        call_command("seed_competence_model", "--replace", stdout=StringIO())
        self.assertEqual(Component.objects.count(), 5)
        self.assertTrue(User.objects.filter(pk=self.teacher_a.pk).exists())


class StatsTests(SimpleTestCase):
    """Namunaviy qiymatlar scipy 1.17 dan olingan (ttest_ind equal_var=False, mannwhitneyu asymptotic
    use_continuity=False, chi2_contingency correction=False, ttest_rel)."""

    A = [72, 65, 88, 91, 54, 77, 83, 69, 95, 60, 74, 81]
    B = [55, 61, 70, 48, 66, 59, 73, 52, 64, 58]

    def test_welch_t(self):
        result = stats.welch_t_test(self.A, self.B)
        self.assertAlmostEqual(result["t"], 3.446702, places=5)
        self.assertAlmostEqual(result["p"], 0.002749261299697454, places=12)

    def test_mann_whitney_with_ties(self):
        self.assertAlmostEqual(stats.mann_whitney(self.A, self.B)["p"], 0.0068621718926084535, places=12)
        self.assertEqual(stats.mann_whitney(self.A, self.B)["u"], 101.0)
        self.assertAlmostEqual(stats.mann_whitney([1, 2, 2, 3, 3, 3, 4], [2, 3, 4, 4, 5, 5])["p"], 0.06662028301124995, places=12)

    def test_chi_square_drops_empty_level(self):
        result = stats.chi_square([[10, 15, 5, 0], [4, 12, 14, 0]])
        self.assertAlmostEqual(result["chi2"], 7.167919799498748, places=10)
        self.assertEqual(result["df"], 2)
        self.assertAlmostEqual(result["p"], 0.027765531553218842, places=12)
        self.assertTrue(result["reliable"])
        self.assertIsNone(stats.chi_square([[3, 0, 0], [5, 0, 0]]))  # hamma bitta darajada — test qo'llanmaydi

    def test_paired_t(self):
        result = stats.paired_t_test([30, 45, 50, 41, 38, 60, 52], [55, 60, 58, 70, 49, 72, 61])
        self.assertAlmostEqual(result["t"], 5.022454885666596, places=10)
        self.assertAlmostEqual(result["p"], 0.0023982026136870095, places=12)

    def test_small_samples_are_not_tested(self):
        self.assertIsNone(stats.welch_t_test([50], [40, 60]))
        self.assertIsNone(stats.paired_t_test([50], [60]))


class EfficiencyTests(CompetenceTests):
    @override_settings(RESEARCH_CONSENT_REQUIRED=False)  # bu test eksport mazmunini tekshiradi, rozilik — users/tests_consent.py
    def test_efficiency_compares_cohorts_and_growth(self):
        self.group_b.ai_enabled = False
        self.group_b.save()
        student_b2 = User.objects.create_user("student_b2", password="x", role=User.Role.STUDENT, group=self.group_b)
        # Tajriba guruhi: 30 → 80, 40 → 90; nazorat: 30 → 50, 40 → 50
        for student, pre, post in ((self.student_a1, 3, 8), (self.student_a2, 4, 9), (self.student_b, 3, 5), (student_b2, 4, 5)):
            self.submit(self.pre, student, pre)
            self.submit(self.post, student, post)
        self.auth_as(self.admin)
        data = self.client.get("/api/competence/efficiency/").data
        row = next(item for item in data["rows"] if item["key"] == str(self.component.pk))
        final = row["stages"]["final"]
        self.assertEqual(final["describe"]["experimental"], {"n": 2, "mean": 85.0, "sd": 7.07})
        self.assertEqual(final["levels"], {"experimental": [0, 0, 2], "control": [0, 2, 0]})
        self.assertEqual(final["efficiency_ratio"], 1.7)
        self.assertLess(final["chi_square"]["p"], 0.05)
        self.assertFalse(final["chi_square"]["reliable"])  # 4 talaba: kutilgan sonlar 5 dan kam
        self.assertEqual(row["growth"]["experimental"]["n"], 2)
        self.assertEqual(row["growth"]["experimental"]["before_mean"], 35.0)
        self.assertEqual(row["growth"]["experimental"]["after_mean"], 85.0)
        # O'sish har ikki talabada bir xil (50) — farqlar dispersiyasi nol, juftlangan t hisoblanmaydi
        self.assertIsNone(row["growth"]["experimental"]["paired"])
        # O'sishlar farqi: tajriba [50, 50], nazorat [20, 10] — tajriba guruhi ko'proq o'sgan
        self.assertGreater(row["growth"]["difference"]["t"], 0)
        self.assertEqual(row["growth"]["control"]["paired"]["mean_diff"], 15.0)

    @override_settings(RESEARCH_CONSENT_REQUIRED=False)  # bu test eksport mazmunini tekshiradi, rozilik — users/tests_consent.py

    def test_delayed_stage_and_retention(self):
        self.group_b.ai_enabled = False
        self.group_b.save()
        delayed = self.make_quiz(Quiz.Kind.DELAYED, "Kechiktirilgan")
        self.quiz_indicator.delayed_quizzes.add(delayed)
        student_b2 = User.objects.create_user("student_b2", password="x", role=User.Role.STUDENT, group=self.group_b)
        # Oxiri → keyin: tajriba guruhi kam unutadi (−5, −5), nazorat ko'p (−20, −10)
        for student, post, later in ((self.student_a1, 8, 7.5), (self.student_a2, 9, 8.5), (self.student_b, 7, 5), (student_b2, 6, 5)):
            self.submit(self.post, student, post)
            self.submit(delayed, student, later)
        later_rows, _ = self.report("delayed")
        self.assertEqual(self.score(later_rows, self.student_a1), {"score": 75.0, "level": "high"})
        self.auth_as(self.admin)
        row = next(item for item in self.client.get("/api/competence/efficiency/").data["rows"] if item["key"] == str(self.component.pk))
        self.assertEqual(row["stages"]["delayed"]["describe"]["experimental"]["mean"], 80.0)
        retention = row["retention"]
        self.assertEqual((retention["experimental"]["before_mean"], retention["experimental"]["after_mean"]), (85.0, 80.0))
        self.assertEqual(retention["control"]["n"], 2)
        self.assertGreater(retention["difference"]["t"], 0)  # tajriba guruhi kamroq unutgan
        stages = self.client.get("/api/competence/model/").data["components"][0]["stages"]
        self.assertEqual(stages, ["initial", "final", "delayed"])

    def test_efficiency_is_staff_only(self):
        self.auth_as(self.student_a1)
        self.assertEqual(self.client.get("/api/competence/efficiency/").status_code, 403)
