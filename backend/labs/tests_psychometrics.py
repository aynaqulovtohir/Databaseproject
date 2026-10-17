"""Laboratoriyalarning psixometrik tahlili: formulalar, 5 daraja, rozilik filtri, ruxsatlar va eksport."""
import csv
import io
import zipfile

from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from users.consent import record_decision
from users.models import StudentGroup, User

from .models import Lab, LabAttempt, LabGrade
from .psychometrics import analyse, cronbach_alpha, lab_queryset, level_of, pearson
from .research import pseudonym

# Talabalar: kuchlidan kuchsizga. Har bir laboratoriya bo'yicha baholar (None — boshlamagan)
GRADES = {
    "oson": [100, 100, 95, 90, 90, 85],
    "qiyin": [40, 20, 10, 10, 0, 0],
    "ajratuvchi": [100, 80, 60, 40, 20, 0],
    "kam": [100, 90, None, None, None, None],
}


class FormulaTests(APITestCase):
    def test_cronbach_alpha(self):
        self.assertEqual(cronbach_alpha([[1, 1], [0, 0], [1, 1], [0, 0]]), 1.0)
        self.assertAlmostEqual(cronbach_alpha([[1, 1], [0, 0], [1, 0], [0, 1]]), 0.0)
        self.assertIsNone(cronbach_alpha([[1, 1], [1, 1]]))  # umumiy ball o'zgarmas
        self.assertIsNone(cronbach_alpha([[1], [0]]))  # bitta laboratoriya

    def test_levels_boundaries(self):
        numbers = [level_of(p)[0] for p in (1.0, 0.81, 0.80, 0.61, 0.60, 0.41, 0.40, 0.21, 0.20, 0.0)]
        self.assertEqual(numbers, [1, 1, 2, 2, 3, 3, 4, 4, 5, 5])

    def test_pearson(self):
        self.assertAlmostEqual(pearson([1, 2, 3], [2, 4, 6]), 1.0)
        self.assertAlmostEqual(pearson([1, 2, 3], [3, 2, 1]), -1.0)
        self.assertIsNone(pearson([1, 1, 1], [1, 2, 3]))
        self.assertIsNone(pearson([1, 2], [1, 2]))


class LabAnalysisTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.group = StudentGroup.objects.create(name="P-guruh", ai_enabled=True)
        cls.other_group = StudentGroup.objects.create(name="P-boshqa")
        cls.teacher = User.objects.create_user("p_teacher", role=User.Role.TEACHER)
        cls.other_teacher = User.objects.create_user("p_teacher2", role=User.Role.TEACHER)
        cls.group.teachers.add(cls.teacher)
        cls.other_group.teachers.add(cls.other_teacher)
        cls.students = [
            User.objects.create_user(f"p_student{index}", role=User.Role.STUDENT, group=cls.group) for index in range(6)
        ]
        for student in cls.students:
            record_decision(student, True)
        # Rozi bo'lmagan talaba: hamma laboratoriyani 0 ga bajargan — tahlilga kirsa natijani o'zgartirardi
        cls.refused = User.objects.create_user("p_refused", role=User.Role.STUDENT, group=cls.group)
        record_decision(cls.refused, False)
        cls.labs = {}
        for title, grades in GRADES.items():
            lab = Lab.objects.create(title=title, description="x", author=cls.teacher)
            lab.groups.add(cls.group)
            cls.labs[title] = lab
            for student, grade in zip(cls.students, grades):
                if grade is not None:
                    cls.grade(lab, student, grade)
            cls.grade(lab, cls.refused, 0)

    @staticmethod
    def grade(lab, student, score):
        attempt = LabAttempt.objects.create(lab=lab, student=student, sql_code="x", is_correct=score >= 60, is_submission=True)
        LabGrade.objects.create(lab=lab, student=student, attempt=attempt, score=score, source=LabGrade.Source.AUTO)

    def setUp(self):
        cache.clear()

    def rows(self, result):
        return {row["title"]: row for row in result["labs"]}

    def test_levels_and_discrimination(self):
        result = analyse(lab_queryset(self.teacher), [self.group])
        rows = self.rows(result)
        self.assertEqual(result["students"], 6)
        self.assertEqual(result["excluded_no_consent"], 1)
        self.assertEqual((rows["oson"]["level"]["number"], rows["oson"]["level"]["label"]), (1, "Juda oson"))
        self.assertEqual(rows["oson"]["p"], 0.93)
        self.assertEqual(rows["qiyin"]["level"]["number"], 5)
        self.assertEqual(rows["ajratuvchi"]["level"]["number"], 3)
        # Kuchli talabalar ajratuvchi laboratoriyani yaxshiroq bajargan
        self.assertGreater(rows["ajratuvchi"]["r"], 0.4)
        self.assertEqual(rows["ajratuvchi"]["discrimination"]["key"], "excellent")
        self.assertEqual(rows["ajratuvchi"]["verdict"]["key"], "good")
        self.assertEqual(rows["oson"]["verdict"]["key"], "review")
        self.assertTrue(rows["oson"]["advice"])
        # 5 tadan kam talaba boshlagan laboratoriya tahlil qilinmaydi va α ga kirmaydi
        self.assertFalse(rows["kam"]["analysed"])
        self.assertIsNone(rows["kam"]["level"])
        self.assertFalse(rows["kam"]["in_reliability"])
        self.assertEqual(rows["kam"]["started"], 2)
        # Taqsimot: 1 juda oson, 1 o'rtacha, 1 juda qiyin
        counts = {item["number"]: item["count"] for item in result["distribution"]}
        self.assertEqual(counts, {1: 1, 2: 0, 3: 1, 4: 0, 5: 1})

    def test_reliability(self):
        reliability = analyse(lab_queryset(self.teacher), [self.group])["reliability"]
        self.assertEqual((reliability["labs"], reliability["students"]), (3, 6))
        matrix = [[GRADES[title][index] / 100 for title in ("oson", "qiyin", "ajratuvchi")] for index in range(6)]
        self.assertEqual(reliability["alpha"], round(cronbach_alpha(matrix), 3))
        self.assertIsNotNone(reliability["interpretation"])
        self.assertIsNotNone(reliability["sem"])

    def test_negative_discrimination_is_flagged(self):
        lab = Lab.objects.create(title="teskari", description="x", author=self.teacher)
        lab.groups.add(self.group)
        for student, score in zip(self.students, [0, 20, 40, 60, 80, 100]):
            self.grade(lab, student, score)
        row = self.rows(analyse(lab_queryset(self.teacher), [self.group]))["teskari"]
        self.assertLess(row["r"], 0)
        self.assertEqual(row["verdict"]["key"], "replace")

    @override_settings(RESEARCH_CONSENT_REQUIRED=False)
    def test_without_consent_requirement_everyone_counts(self):
        result = analyse(lab_queryset(self.teacher), [self.group])
        self.assertEqual((result["students"], result["excluded_no_consent"]), (7, 0))

    def test_api_access(self):
        url = "/api/statistics/labs-analysis/"
        self.client.force_authenticate(self.students[0])
        self.assertEqual(self.client.get(url).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.other_teacher)
        self.assertEqual(self.client.get(url, {"group": self.group.pk}).status_code, status.HTTP_404_NOT_FOUND)
        # Boshqa o'qituvchi bu laboratoriyalarni ko'rmaydi
        self.assertEqual(self.client.get(url).data["labs"], [])
        self.assertEqual(self.client.get(url, {"group": "x"}).status_code, status.HTTP_400_BAD_REQUEST)
        self.client.force_authenticate(self.teacher)
        response = self.client.get(url, {"group": self.group.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["labs"]), 4)

    def test_export_has_analysis_and_skips_refused_student(self):
        self.client.force_authenticate(self.teacher)
        response = self.client.get("/api/labs/research-export/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        everything = "".join(archive.read(name).decode("utf-8-sig") for name in archive.namelist())
        self.assertNotIn(pseudonym(self.refused.pk), everything)
        self.assertIn(pseudonym(self.students[0].pk), everything)
        rows = list(csv.DictReader(io.StringIO(archive.read("laboratoriyalar_tahlili.csv").decode("utf-8-sig")), delimiter=";"))
        by_title = {row["laboratoriya"]: row for row in rows}
        self.assertEqual(by_title["qiyin"]["daraja"], "5")
        self.assertEqual(by_title["qiyin"]["daraja_nomi"], "Juda qiyin")
        self.assertEqual(by_title["kam"]["daraja"], "")
        self.assertEqual(rows[-1]["laboratoriya_id"], "alfa")
        self.assertIn("rozilik bergan talabalar", archive.read("README.txt").decode("utf-8-sig"))
