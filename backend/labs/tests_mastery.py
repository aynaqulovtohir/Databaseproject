"""Moslashuvchan o'quv yo'li: BKT hisoblari va tavsiya."""
from django.test import SimpleTestCase
from rest_framework import status

from .mastery import MASTERED, P_INIT, observations, update
from .models import Lab, LabAttempt
from .tests import BaseTestCase


class BktMathTests(SimpleTestCase):
    def test_correct_raises_and_wrong_lowers(self):
        self.assertGreater(update(P_INIT, True), P_INIT)
        self.assertLess(update(0.6, False), 0.6)
        value = P_INIT
        for _ in range(6):
            value = update(value, True)
        self.assertGreater(value, MASTERED)

    def test_observations_stop_at_first_correct_and_are_capped(self):
        class A:
            def __init__(self, ok):
                self.is_correct = ok

        self.assertEqual(observations([A(False), A(True), A(False)]), [False, True])
        self.assertEqual(observations([A(False)] * 10), [False, False, False])


class RecommendationTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # cls.lab — SELECT mavzusi; ER va indeks mavzulari ham bor
        cls.er_lab = Lab.objects.create(kind=Lab.Kind.ER, title="ER", description="x", author=cls.teacher_a,
                                        reference_diagram={"entities": [], "relationships": []})
        cls.er_lab.groups.add(cls.group_a)
        cls.select2 = Lab.objects.create(title="SELECT 2", description="x", setup_sql="", author=cls.teacher_a,
                                         topic=Lab.Topic.SELECT)
        cls.select2.groups.add(cls.group_a)

    def test_topics_are_derived(self):
        self.assertEqual(self.lab.effective_topic, "select")
        self.assertEqual(self.er_lab.effective_topic, "er")

    def test_student_gets_earliest_unmastered_topic(self):
        self.auth_as(self.student_a1)
        data = self.client.get("/api/labs/recommendations/").data
        self.assertEqual([item["topic"] for item in data["topics"]], ["er", "select"])
        self.assertEqual(data["next"]["id"], self.er_lab.pk)  # kurs tartibida birinchi mavzu

        # ER ni bir necha marta to'g'ri yechsa ham bitta laboratoriya — mavzu hali o'zlashtirilmagan bo'lishi mumkin,
        # lekin yechilgan laboratoriya qayta tavsiya qilinmaydi
        LabAttempt.objects.create(lab=self.er_lab, student=self.student_a1, is_correct=True)
        data = self.client.get("/api/labs/recommendations/").data
        self.assertEqual(data["next"]["topic"], "select")
        er = next(item for item in data["topics"] if item["topic"] == "er")
        self.assertEqual((er["labs"], er["solved"]), (1, 1))
        self.assertGreater(er["mastery"], 20)

    def test_failures_lower_mastery(self):
        for _ in range(3):
            LabAttempt.objects.create(lab=self.lab, student=self.student_a1, is_correct=False)
        self.auth_as(self.student_a1)
        select = next(item for item in self.client.get("/api/labs/recommendations/").data["topics"] if item["topic"] == "select")
        self.assertLess(select["mastery"], 20)

    def test_teacher_group_view_and_permissions(self):
        LabAttempt.objects.create(lab=self.lab, student=self.student_a1, is_correct=True)
        self.auth_as(self.teacher_a)
        response = self.client.get("/api/labs/recommendations/", {"group": self.group_a.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = next(item for item in response.data["students"] if item["id"] == self.student_a1.pk)
        self.assertIn("select", row["mastery"])
        self.assertEqual(self.client.get("/api/labs/recommendations/", {"group": self.group_b.pk}).status_code, 404)
        self.assertEqual(self.client.get("/api/labs/recommendations/").status_code, 400)
