"""Imtihon rejimi: imtihondan oldin yopiq, paytida AI'siz, keyin faqat ko'rish."""
from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone
from rest_framework import status

from .models import Lab, LabAttempt, LabModule
from .tests import ER_REFERENCE, ER_WRONG, SOLUTION, BaseTestCase


@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="test-key")
class ExamModeTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.module = LabModule.objects.create(title="Imtihon", sequential=False, author=cls.teacher_a)
        cls.lab.module = cls.module
        cls.lab.save()
        cls.er_lab = Lab.objects.create(
            kind=Lab.Kind.ER, title="ER imtihon", description="d", reference_diagram=ER_REFERENCE,
            author=cls.teacher_a, module=cls.module,
        )
        cls.er_lab.groups.add(cls.group_a)

    def set_exam(self, starts_in_minutes, length_minutes=60):
        now = timezone.now()
        self.module.exam_starts_at = now + timedelta(minutes=starts_in_minutes)
        self.module.exam_ends_at = self.module.exam_starts_at + timedelta(minutes=length_minutes)
        self.module.save()

    def test_before_exam_lab_is_closed_and_hidden(self):
        self.set_exam(30)
        self.auth_as(self.student_a1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("boshlanadi", response.data["detail"])
        listed = next(item for item in self.client.get("/api/labs/").data if item["id"] == self.lab.pk)
        self.assertEqual(listed["description"], "")
        self.assertEqual(listed["module_detail"]["exam"]["state"], "upcoming")
        self.assertEqual(self.run_code(SOLUTION).status_code, status.HTTP_403_FORBIDDEN)
        # O'qituvchi uchun cheklov yo'q
        self.auth_as(self.teacher_a)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_200_OK)

    def test_during_exam_work_is_allowed_but_ai_is_off(self):
        self.set_exam(-10)
        self.auth_as(self.student_a1)
        response = self.run_code("SELECT 1;")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["ai_available"])
        attempt = LabAttempt.objects.get(pk=response.data["attempt_id"])
        response = self.client.post(f"/api/labs/attempts/{attempt.pk}/advice/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Imtihon davomida", response.data["detail"])
        self.assertEqual(self.client.get(f"/api/labs/{self.lab.pk}/chat/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(f"/api/labs/{self.lab.pk}/study-advice/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(f"/api/labs/{self.er_lab.pk}/peer-review/").status_code, status.HTTP_403_FORBIDDEN)

    def test_during_exam_grading_is_automatic(self):
        self.set_exam(-10)
        self.auth_as(self.student_a1)
        with patch("labs.views.ai_grade") as ai_grade:
            response = self.client.post(f"{self.url}submit/", {"sql_code": SOLUTION}, format="json")
        ai_grade.assert_not_called()
        self.assertEqual(response.data["grade"]["source"], "auto")
        self.assertEqual(response.data["grade"]["score"], 100)

    def test_during_exam_er_fix_is_hidden_until_the_end(self):
        self.set_exam(-10)
        self.auth_as(self.student_a1)
        response = self.client.post(f"/api/labs/{self.er_lab.pk}/submit/", {"diagram": ER_WRONG}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIsNone(response.data["fix"])
        progress = self.client.get(f"/api/labs/{self.er_lab.pk}/").data["my_progress"]
        self.assertIsNone(progress["last_fix"])
        # Saqlangan, imtihon tugagach ko'rinadi
        self.assertTrue(LabAttempt.objects.get(pk=response.data["attempt_id"]).fixed_diagram)
        self.set_exam(-120)
        progress = self.client.get(f"/api/labs/{self.er_lab.pk}/").data["my_progress"]
        self.assertIsNotNone(progress["last_fix"])

    def test_after_exam_lab_is_read_only(self):
        self.set_exam(-120)
        self.auth_as(self.student_a1)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_200_OK)
        response = self.run_code(SOLUTION)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("tugagan", response.data["detail"])
        self.assertEqual(self.client.post(f"{self.url}submit/", {"sql_code": SOLUTION}, format="json").status_code, 403)

    def test_module_validation(self):
        self.auth_as(self.teacher_a)
        url = f"/api/lab-modules/{self.module.pk}/"
        start = timezone.now() + timedelta(days=1)
        response = self.client.patch(url, {"exam_starts_at": start.isoformat()}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.patch(
            url, {"exam_starts_at": start.isoformat(), "exam_ends_at": (start - timedelta(hours=1)).isoformat()}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.patch(
            url, {"exam_starts_at": start.isoformat(), "exam_ends_at": (start + timedelta(hours=1)).isoformat()}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        response = self.client.patch(url, {"exam_starts_at": None, "exam_ends_at": None}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.module.refresh_from_db()
        self.assertIsNone(self.module.exam_starts_at)

    def test_no_exam_means_no_restrictions(self):
        self.auth_as(self.student_a1)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_200_OK)
        self.assertIsNone(self.client.get(self.url).data["module_detail"]["exam"])
