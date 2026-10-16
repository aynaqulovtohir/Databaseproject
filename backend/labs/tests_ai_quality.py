"""AI sifatini nazorat qilish: navbat, baholash, ruxsatlar va xulosa (Wilson oralig'i)."""
from django.test import SimpleTestCase
from rest_framework import status

from .ai_quality import wilson
from .models import AIOutputReview, LabAttempt
from .tests import BaseTestCase

URL = "/api/ai-quality/"


class WilsonTests(SimpleTestCase):
    def test_interval(self):
        self.assertIsNone(wilson(0, 0))
        low, high = wilson(5, 50)
        self.assertLess(low, 10)
        self.assertGreater(high, 10)
        self.assertEqual(wilson(0, 20)[0], 0.0)
        self.assertEqual(wilson(20, 20)[1], 100.0)


class AIQualityApiTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.with_hints = LabAttempt.objects.create(
            lab=cls.lab, student=cls.student_a1, sql_code="SELECT 1", is_correct=False,
            ai_hints=["Shartni qayta o'qing.", "WHERE bilan narxni filtrlang."], ai_hint_level=2,
        )
        cls.explained = LabAttempt.objects.create(
            lab=cls.lab, student=cls.student_a2, sql_code="SELECT 1", is_correct=True,
            self_explanation="Narx bo'yicha filtrladim", explanation_verdict="partial", explanation_feedback="Saralashni ham tushuntiring.",
        )
        # Boshqa guruh — teacher_a ga ko'rinmaydi
        LabAttempt.objects.create(lab=cls.lab, student=cls.student_b, sql_code="x", is_correct=False, ai_hints=["Boshqa guruh"])

    def rate(self, item, rating="helpful"):
        return self.client.post(URL, {"attempt": item["attempt"], "kind": item["kind"], "level": item["level"], "rating": rating}, format="json")

    def test_teacher_rates_all_items_of_own_groups(self):
        self.auth_as(self.teacher_a)
        seen = []
        data = self.client.get(URL).data
        self.assertNotIn("student_a1", str(data["next"]))
        while data["next"]:
            item = data["next"]
            seen.append((item["attempt"], item["kind"], item["level"]))
            self.assertNotEqual(item["text"], "Boshqa guruh")
            response = self.rate(item, "wrong" if item["level"] == 2 else "helpful")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
            data = response.data
        self.assertCountEqual(
            seen,
            [(self.with_hints.pk, "hint", 1), (self.with_hints.pk, "hint", 2), (self.explained.pk, "explanation", 0)],
        )
        hints = next(item for item in data["summary"] if item["kind"] == "hint")
        self.assertEqual(hints["total"], 2)
        wrong = next(item for item in hints["ratings"] if item["rating"] == "wrong")
        self.assertEqual((wrong["count"], wrong["percent"]), (1, 50.0))
        self.assertEqual(data["rated_by_me"], 3)

    def test_validation_and_scope(self):
        self.auth_as(self.teacher_a)
        item = self.client.get(URL).data["next"]
        self.assertEqual(self.rate(item, "zo'r").status_code, status.HTTP_400_BAD_REQUEST)
        bad_level = {**item, "level": 9}
        self.assertEqual(self.rate(bad_level).status_code, status.HTTP_400_BAD_REQUEST)
        other = LabAttempt.objects.get(student=self.student_b)
        self.assertEqual(self.rate({"attempt": other.pk, "kind": "hint", "level": 1}).status_code, status.HTTP_404_NOT_FOUND)
        # Qayta baholash yangisini yaratmaydi, o'zgartiradi
        self.rate(item, "helpful")
        self.rate(item, "unclear")
        self.assertEqual(AIOutputReview.objects.get().rating, "unclear")

    def test_students_cannot_access(self):
        self.auth_as(self.student_a1)
        self.assertEqual(self.client.get(URL).status_code, status.HTTP_403_FORBIDDEN)
