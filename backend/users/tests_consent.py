"""Tadqiqotga rozilik: so'rash, qaror berish, qaytarib olish, tarix va sozlama."""
from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from .consent import participant_ids, research_participants
from .models import ResearchConsent, StudentGroup, User

URL = "/api/auth/consent/"


class ConsentTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.group = StudentGroup.objects.create(name="R-guruh")
        cls.student = User.objects.create_user("r_student", role=User.Role.STUDENT, group=cls.group)
        cls.teacher = User.objects.create_user("r_teacher", role=User.Role.TEACHER)

    def setUp(self):
        cache.clear()

    def me(self):
        return self.client.get("/api/auth/me/").data

    def test_student_is_asked_staff_is_not(self):
        self.client.force_authenticate(self.student)
        self.assertTrue(self.me()["consent_needed"])
        data = self.client.get(URL).data
        self.assertIsNone(data["agreed"])
        self.assertTrue(data["text"])
        self.client.force_authenticate(self.teacher)
        self.assertFalse(self.me()["consent_needed"])

    def test_agree_and_withdraw_are_recorded(self):
        self.client.force_authenticate(self.student)
        response = self.client.post(URL, {"agreed": True}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["agreed"])
        self.assertFalse(self.me()["consent_needed"])
        self.assertEqual(participant_ids(), {self.student.pk})

        self.client.post(URL, {"agreed": False}, format="json")
        self.assertEqual(participant_ids(), set())
        self.assertFalse(research_participants(User.objects.all()).exists())
        # Qaror bergan — qayta so'ralmaydi; tarixda ikkala qaror bor
        self.assertFalse(self.me()["consent_needed"])
        self.assertEqual(list(ResearchConsent.objects.filter(user=self.student).values_list("agreed", flat=True)), [False, True])

    def test_invalid_requests(self):
        self.client.force_authenticate(self.student)
        for value in ("true", 1, None):
            response = self.client.post(URL, {"agreed": value}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.post(URL, {"agreed": True}, format="json").status_code, status.HTTP_400_BAD_REQUEST)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(URL).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_new_text_version_asks_again_but_keeps_previous_decision(self):
        self.client.force_authenticate(self.student)
        self.client.post(URL, {"agreed": True}, format="json")
        with patch("users.consent.CONSENT_VERSION", "2"):
            self.assertTrue(self.me()["consent_needed"])
            self.assertEqual(participant_ids(), {self.student.pk})

    @override_settings(RESEARCH_CONSENT_REQUIRED=False)
    def test_disabled(self):
        self.client.force_authenticate(self.student)
        self.assertFalse(self.me()["consent_needed"])
        self.assertIsNone(participant_ids())
        self.assertEqual(research_participants(User.objects.all()).count(), 2)
