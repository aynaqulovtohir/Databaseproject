"""Erta ogohlantirish: xavf signallari, darajalar, ruxsatlar va haftalik Telegram xulosasi."""
from datetime import timedelta

from django.test import override_settings
from django.utils import timezone
from rest_framework import status

from notifications.models import Notification, TelegramAccount
from notifications.services import create_risk_digests
from users.models import User

from .models import Lab, LabAttempt
from .risk import STUCK_ATTEMPTS, digest_text, group_risk, level_of
from .tests import PASSWORD, BaseTestCase


class RiskTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.student_a3 = User.objects.create_user("student_a3", password=PASSWORD, role=User.Role.STUDENT, group=cls.group_a, first_name="Laylo")
        cls.labs = [cls.lab]
        for number in range(3):
            lab = Lab.objects.create(title=f"Lab {number}", description="x", setup_sql="", author=cls.teacher_a)
            lab.groups.add(cls.group_a)
            cls.labs.append(lab)

    def attempt(self, student, lab, correct, days_ago=0):
        attempt = LabAttempt.objects.create(lab=lab, student=student, sql_code="x", is_correct=correct)
        if days_ago:
            LabAttempt.objects.filter(pk=attempt.pk).update(created_at=timezone.now() - timedelta(days=days_ago))
        return attempt

    def rows(self):
        return {row["id"]: row for row in group_risk(self.group_a)["students"]}

    def codes(self, student):
        return [reason["code"] for reason in self.rows()[student.pk]["reasons"]]

    def test_levels(self):
        self.assertEqual([level_of(score) for score in (0, 1, 2, 3, 5)], ["none", "low", "medium", "high", "high"])

    def test_inactive_and_behind(self):
        # a2 va a3 hamma laboratoriyani yechgan (mediana 4), a1 — bittasini, 10 kun oldin
        for student in (self.student_a2, self.student_a3):
            for lab in self.labs:
                self.attempt(student, lab, True)
        self.attempt(self.student_a1, self.labs[0], True, days_ago=10)
        row = self.rows()[self.student_a1.pk]
        self.assertEqual([reason["code"] for reason in row["reasons"]], ["inactive", "behind"])
        self.assertEqual((row["level"], row["score"]), ("high", 4))
        self.assertIn("10 kundan beri", row["reasons"][0]["text"])
        self.assertEqual(self.rows()[self.student_a2.pk]["level"], "none")
        # Ro'yxat yuqori xavfdan boshlanadi
        self.assertEqual(group_risk(self.group_a)["students"][0]["id"], self.student_a1.pk)

    def test_no_activity_at_all(self):
        self.assertEqual(self.codes(self.student_a1), ["inactive"])
        self.assertIn("hech qanday faollik", self.rows()[self.student_a1.pk]["reasons"][0]["text"])

    def test_stuck_in_one_lab(self):
        for _ in range(STUCK_ATTEMPTS):
            self.attempt(self.student_a1, self.labs[1], False)
        self.assertIn("stuck", self.codes(self.student_a1))
        self.attempt(self.student_a1, self.labs[1], True)  # yechgach signal yo'qoladi
        self.assertNotIn("stuck", self.codes(self.student_a1))

    def test_access(self):
        self.auth_as(self.student_a1)
        self.assertEqual(self.client.get("/api/risk/", {"group": self.group_a.pk}).status_code, status.HTTP_403_FORBIDDEN)
        self.auth_as(self.teacher_b)
        self.assertEqual(self.client.get("/api/risk/", {"group": self.group_a.pk}).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get("/api/risk/", {"group": "x"}).status_code, status.HTTP_400_BAD_REQUEST)
        self.auth_as(self.teacher_a)
        response = self.client.get("/api/risk/", {"group": self.group_a.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["students"]), 3)

    def test_digest_only_high_risk(self):
        for student in (self.student_a1, self.student_a2, self.student_a3):
            for lab in self.labs:
                self.attempt(student, lab, True)
        self.assertIsNone(digest_text([self.group_a]))
        LabAttempt.objects.filter(student=self.student_a3).delete()
        self.attempt(self.student_a3, self.labs[0], False, days_ago=9)
        text = digest_text([self.group_a])
        self.assertIn("Laylo", text)
        self.assertNotIn(self.student_a1.username, text)

    @override_settings(TELEGRAM_BOT_TOKEN="test", TELEGRAM_BOT_USERNAME="test_bot")
    def test_weekly_digest_is_sent_once(self):
        TelegramAccount.objects.create(user=self.teacher_a, chat_id=111)
        # a1: 9 kundan beri faol emas va guruhdan orqada (yuqori xavf); faqat o'rta xavf xulosaga kirmaydi
        for student in (self.student_a2, self.student_a3):
            for lab in self.labs:
                self.attempt(student, lab, True)
        self.attempt(self.student_a1, self.labs[0], False, days_ago=9)
        self.assertEqual(create_risk_digests(), 1)
        self.assertEqual(create_risk_digests(), 0)  # bir hafta ichida takrorlanmaydi
        notification = Notification.objects.get(kind=Notification.Kind.RISK_DIGEST)
        self.assertEqual(notification.user, self.teacher_a)
        self.assertIn("A-guruh", notification.text)
