"""Telegram bog'lanishi va bildirishnomalar testlari.

Haqiqiy Telegram chaqirilmaydi: `requests.post` o'rniga soxta (mock) javob qo'yiladi.
"""
from datetime import timedelta
from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from learning.models import Assignment
from submissions.models import Submission
from users.models import StudentGroup, User

from . import bot, linking, services, telegram
from .models import Notification, TelegramAccount, TelegramLinkCode

PASSWORD = "Kuchli-Parol-2026"
SQL = "CREATE TABLE kitob (id SERIAL PRIMARY KEY);"
TOKEN = "123456:MAXFIY-TOKEN"
CONFIGURED = {"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_BOT_USERNAME": "test_bot"}


def telegram_ok(result=True):
    response = MagicMock()
    response.json.return_value = {"ok": True, "result": result}
    return response


def telegram_error(code, description):
    response = MagicMock()
    response.json.return_value = {"ok": False, "error_code": code, "description": description}
    return response


class DataMixin:
    @classmethod
    def setUpTestData(cls):
        cls.group = StudentGroup.objects.create(name="MAXFIY-GURUH")
        cls.other_group = StudentGroup.objects.create(name="B-guruh")
        cls.admin = User.objects.create_user("admin1", password=PASSWORD, role=User.Role.ADMIN)
        cls.teacher = User.objects.create_user(
            "teacher1", password=PASSWORD, role=User.Role.TEACHER, first_name="Ustozismi"
        )
        cls.student = User.objects.create_user(
            "student1", password=PASSWORD, role=User.Role.STUDENT, group=cls.group, first_name="Maxfiyism"
        )
        cls.unlinked_student = User.objects.create_user(
            "student2", password=PASSWORD, role=User.Role.STUDENT, group=cls.group
        )
        cls.other_student = User.objects.create_user(
            "student3", password=PASSWORD, role=User.Role.STUDENT, group=cls.other_group
        )
        cls.group.teachers.add(cls.teacher)
        TelegramAccount.objects.create(user=cls.student, chat_id=111)
        TelegramAccount.objects.create(user=cls.teacher, chat_id=222)
        TelegramAccount.objects.create(user=cls.other_student, chat_id=333)

    def setUp(self):
        cache.clear()

    def make_assignment(self, hours=72, title="Kutubxona bazasi"):
        assignment = Assignment.objects.create(
            title=title,
            description="Baza loyihalang",
            author=self.teacher,
            deadline=timezone.now() + timedelta(hours=hours),
        )
        assignment.groups.add(self.group)
        return assignment

    def kinds_for(self, user):
        return list(Notification.objects.filter(user=user).values_list("kind", flat=True))


@override_settings(**CONFIGURED)
class EventTests(DataMixin, APITestCase):
    def auth_as(self, user):
        response = self.client.post("/api/auth/login/", {"username": user.username, "password": PASSWORD})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_new_assignment_notifies_linked_group_students_only(self):
        self.make_assignment()
        self.assertEqual(self.kinds_for(self.student), ["new_assignment"])
        self.assertEqual(self.kinds_for(self.unlinked_student), [])
        self.assertEqual(self.kinds_for(self.other_student), [])
        self.assertEqual(self.kinds_for(self.teacher), [])

    def test_assignment_created_via_api_notifies(self):
        self.auth_as(self.teacher)
        response = self.client.post(
            "/api/assignments/",
            {
                "title": "Do'kon bazasi",
                "description": "x",
                "groups": [self.group.pk],
                "deadline": (timezone.now() + timedelta(days=3)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        notification = Notification.objects.get(user=self.student)
        self.assertIn("Do'kon bazasi", notification.text)
        self.assertIn("Muddat:", notification.text)

    def test_adding_group_later_notifies_only_new_group(self):
        assignment = self.make_assignment()
        Notification.objects.all().delete()
        assignment.groups.add(self.other_group)
        self.assertEqual(self.kinds_for(self.other_student), ["new_assignment"])
        self.assertEqual(self.kinds_for(self.student), [])

    def test_submission_grade_and_return_flow(self):
        assignment = self.make_assignment()
        Notification.objects.all().delete()

        self.auth_as(self.student)
        submission_id = self.client.post(
            f"/api/assignments/{assignment.pk}/submissions/", {"sql_code": SQL}, format="json"
        ).data["id"]
        self.assertEqual(self.kinds_for(self.teacher), ["new_submission"])

        self.auth_as(self.teacher)
        self.client.put(f"/api/submissions/{submission_id}/grade/", {"score": 60, "comment": "MAXFIY-IZOH"}, format="json")
        self.assertEqual(self.kinds_for(self.student), ["graded"])
        # Baho o'zgartirilganda qayta xabar bormaydi
        self.client.put(f"/api/submissions/{submission_id}/grade/", {"score": 65}, format="json")
        self.assertEqual(self.kinds_for(self.student), ["graded"])

        self.client.post(f"/api/submissions/{submission_id}/return/", {"comment": "MAXFIY-IZOH"}, format="json")
        self.assertEqual(self.kinds_for(self.student), ["graded", "returned"])

    def test_messages_contain_no_personal_data_score_or_comment(self):
        assignment = self.make_assignment()
        submission = Submission.objects.create(
            assignment=assignment, student=self.student, sql_code=SQL, attempt_number=1
        )
        self.auth_as(self.teacher)
        self.client.put(f"/api/submissions/{submission.pk}/grade/", {"score": 87, "comment": "MAXFIY-IZOH"}, format="json")
        self.client.post(f"/api/submissions/{submission.pk}/return/", {"comment": "MAXFIY-IZOH"}, format="json")
        services.create_deadline_reminders()

        texts = " | ".join(Notification.objects.values_list("text", flat=True))
        self.assertEqual(Notification.objects.count(), 4)
        for secret in ("Maxfiyism", "student1", "Ustozismi", "teacher1", "MAXFIY-GURUH", "MAXFIY-IZOH", "87"):
            self.assertNotIn(secret, texts)

    def test_inactive_user_is_not_notified(self):
        User.objects.filter(pk=self.student.pk).update(is_active=False)
        self.make_assignment()
        self.assertEqual(self.kinds_for(self.student), [])

    @override_settings(TELEGRAM_BOT_TOKEN="")
    def test_nothing_is_queued_when_not_configured(self):
        self.make_assignment()
        self.assertEqual(Notification.objects.count(), 0)

    def test_long_title_is_shortened(self):
        self.make_assignment(title="A" * 200)
        self.assertLess(len(Notification.objects.get().text), 180)


@override_settings(**CONFIGURED)
class DeadlineReminderTests(DataMixin, TestCase):
    def test_reminder_for_students_who_have_not_submitted(self):
        assignment = self.make_assignment(hours=10)
        Notification.objects.all().delete()
        self.assertEqual(services.create_deadline_reminders(), 1)
        notification = Notification.objects.get()
        self.assertEqual((notification.user, notification.kind), (self.student, "deadline_reminder"))
        self.assertIn(assignment.title, notification.text)

    def test_reminder_is_sent_only_once(self):
        self.make_assignment(hours=10)
        services.create_deadline_reminders()
        self.assertEqual(services.create_deadline_reminders(), 0)
        self.assertEqual(Notification.objects.filter(kind="deadline_reminder").count(), 1)

    def test_no_reminder_if_already_submitted(self):
        assignment = self.make_assignment(hours=10)
        Submission.objects.create(assignment=assignment, student=self.student, sql_code=SQL, attempt_number=1)
        self.assertEqual(services.create_deadline_reminders(), 0)

    def test_no_reminder_for_far_or_past_deadlines(self):
        self.make_assignment(hours=48)
        past = self.make_assignment(hours=10)
        Assignment.objects.filter(pk=past.pk).update(deadline=timezone.now() - timedelta(hours=1))
        self.assertEqual(services.create_deadline_reminders(), 0)


@override_settings(**CONFIGURED)
class LinkApiTests(DataMixin, APITestCase):
    def auth_as(self, user):
        response = self.client.post("/api/auth/login/", {"username": user.username, "password": PASSWORD})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_anonymous_rejected(self):
        self.assertEqual(self.client.get("/api/telegram/").status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.post("/api/telegram/link/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_status(self):
        self.auth_as(self.unlinked_student)
        self.assertEqual(self.client.get("/api/telegram/").data, {"configured": True, "linked": False, "linked_at": None})
        self.auth_as(self.student)
        data = self.client.get("/api/telegram/").data
        self.assertTrue(data["linked"])
        self.assertNotIn("chat_id", data)

    def test_link_flow(self):
        self.auth_as(self.unlinked_student)
        response = self.client.post("/api/telegram/link/")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        url = response.data["url"]
        self.assertTrue(url.startswith("https://t.me/test_bot?start="))
        code = url.split("start=")[1]
        # Bazada kodning o'zi saqlanmaydi
        self.assertNotEqual(TelegramLinkCode.objects.get(user=self.unlinked_student).code_hash, code)

        with patch("notifications.telegram.requests.post", return_value=telegram_ok()) as post:
            bot.handle_update({"update_id": 1, "message": {"chat": {"id": 999, "type": "private"}, "text": f"/start {code}"}})
        self.assertEqual(TelegramAccount.objects.get(user=self.unlinked_student).chat_id, 999)
        self.assertEqual(post.call_args.kwargs["json"]["text"], bot.TEXT_LINKED)
        self.assertTrue(self.client.get("/api/telegram/").data["linked"])
        # Kod bir martalik
        self.assertFalse(linking.link_chat(code, 12345))

    def test_unlink(self):
        self.auth_as(self.student)
        self.assertEqual(self.client.delete("/api/telegram/").status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TelegramAccount.objects.filter(user=self.student).exists())
        self.assertTrue(TelegramAccount.objects.filter(user=self.teacher).exists())

    @override_settings(TELEGRAM_BOT_USERNAME="")
    def test_link_unavailable_when_not_configured(self):
        self.auth_as(self.student)
        self.assertEqual(self.client.post("/api/telegram/link/").status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertFalse(self.client.get("/api/telegram/").data["configured"])


@override_settings(**CONFIGURED)
class LinkingTests(DataMixin, TestCase):
    def code_for(self, user):
        return linking.create_link(user)[0].split("start=")[1]

    def test_wrong_and_expired_codes_rejected(self):
        code = self.code_for(self.unlinked_student)
        self.assertFalse(linking.link_chat("notogri-kod", 999))
        TelegramLinkCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertFalse(linking.link_chat(code, 999))
        self.assertFalse(TelegramAccount.objects.filter(user=self.unlinked_student).exists())

    def test_new_code_invalidates_old_one(self):
        old_code = self.code_for(self.unlinked_student)
        new_code = self.code_for(self.unlinked_student)
        self.assertFalse(linking.link_chat(old_code, 999))
        self.assertTrue(linking.link_chat(new_code, 999))

    def test_inactive_user_cannot_link(self):
        code = self.code_for(self.unlinked_student)
        User.objects.filter(pk=self.unlinked_student.pk).update(is_active=False)
        self.assertFalse(linking.link_chat(code, 999))

    def test_one_chat_belongs_to_one_user(self):
        code = self.code_for(self.unlinked_student)
        self.assertTrue(linking.link_chat(code, 111))  # 111 avval student1 ga tegishli edi
        self.assertFalse(TelegramAccount.objects.filter(user=self.student).exists())
        self.assertEqual(TelegramAccount.objects.get(chat_id=111).user, self.unlinked_student)

    def test_relinking_replaces_chat(self):
        code = self.code_for(self.student)
        self.assertTrue(linking.link_chat(code, 444))
        self.assertEqual(TelegramAccount.objects.get(user=self.student).chat_id, 444)


@override_settings(**CONFIGURED)
class BotCommandTests(DataMixin, TestCase):
    def send(self, text, chat_id=111, chat_type="private"):
        with patch("notifications.telegram.requests.post", return_value=telegram_ok()) as post:
            bot.handle_update({"update_id": 1, "message": {"chat": {"id": chat_id, "type": chat_type}, "text": text}})
        return post.call_args.kwargs["json"]["text"] if post.called else None

    def test_start_without_code(self):
        self.assertEqual(self.send("/start"), bot.TEXT_START_WITHOUT_CODE)

    def test_start_with_bad_code(self):
        self.assertEqual(self.send("/start yomon-kod", chat_id=999), bot.TEXT_BAD_CODE)

    def test_stop_unlinks(self):
        self.assertEqual(self.send("/stop"), bot.TEXT_UNLINKED)
        self.assertFalse(TelegramAccount.objects.filter(chat_id=111).exists())
        self.assertEqual(self.send("/stop"), bot.TEXT_NOT_LINKED)

    def test_other_text_gets_help(self):
        self.assertEqual(self.send("salom"), bot.TEXT_HELP)

    def test_group_chats_and_non_text_are_ignored(self):
        self.assertIsNone(self.send("/stop", chat_type="group"))
        self.assertTrue(TelegramAccount.objects.filter(chat_id=111).exists())
        with patch("notifications.telegram.requests.post") as post:
            bot.handle_update({"update_id": 2, "message": {"chat": {"id": 111, "type": "private"}}})
            bot.handle_update({"update_id": 3})
        post.assert_not_called()


@override_settings(**CONFIGURED)
class SendTests(DataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.notification = Notification.objects.create(user=self.student, kind="graded", text="Matn")

    def test_sends_to_linked_chat(self):
        with patch("notifications.telegram.requests.post", return_value=telegram_ok()) as post:
            self.assertEqual(bot.send_pending(), 1)
        self.assertEqual(post.call_args.kwargs["json"], {"chat_id": 111, "text": "Matn"})
        self.assertIn("/sendMessage", post.call_args.args[0])
        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, "sent")
        self.assertIsNotNone(self.notification.sent_at)
        # Ikkinchi marta yuborilmaydi
        with patch("notifications.telegram.requests.post", return_value=telegram_ok()) as post:
            self.assertEqual(bot.send_pending(), 0)
        post.assert_not_called()

    def test_blocked_bot_unlinks_user(self):
        error = telegram_error(403, "Forbidden: bot was blocked by the user")
        with patch("notifications.telegram.requests.post", return_value=error):
            bot.send_pending()
        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, "failed")
        self.assertFalse(TelegramAccount.objects.filter(user=self.student).exists())

    def test_transient_error_retries_then_fails(self):
        error = telegram_error(429, "Too Many Requests")
        with patch("notifications.telegram.requests.post", return_value=error):
            for expected in ("pending", "pending", "failed"):
                bot.send_pending()
                self.notification.refresh_from_db()
                self.assertEqual(self.notification.status, expected)
        self.assertEqual(self.notification.attempts, 3)
        self.assertTrue(TelegramAccount.objects.filter(user=self.student).exists())

    def test_network_error_is_transient_and_hides_token(self):
        network_error = requests.ConnectionError(f"https://api.telegram.org/bot{TOKEN}/sendMessage failed")
        with patch("notifications.telegram.requests.post", side_effect=network_error):
            with self.assertRaises(telegram.TelegramTransientError) as caught:
                telegram.send_message(111, "x")
            bot.send_pending()
        self.assertNotIn(TOKEN, str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)
        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, "pending")
        self.assertNotIn(TOKEN, self.notification.error_message)

    def test_unlinked_or_inactive_user_is_skipped(self):
        TelegramAccount.objects.filter(user=self.student).delete()
        inactive = Notification.objects.create(user=self.other_student, kind="graded", text="Matn")
        User.objects.filter(pk=self.other_student.pk).update(is_active=False)
        with patch("notifications.telegram.requests.post", return_value=telegram_ok()) as post:
            self.assertEqual(bot.send_pending(), 0)
        post.assert_not_called()
        for notification in (self.notification, inactive):
            notification.refresh_from_db()
            self.assertEqual(notification.status, "failed")

    def test_bad_token_is_permanent_error(self):
        with patch("notifications.telegram.requests.post", return_value=telegram_error(401, "Unauthorized")):
            bot.send_pending()
        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, "failed")

    @override_settings(TELEGRAM_BOT_TOKEN="")
    def test_not_configured(self):
        with self.assertRaises(telegram.TelegramNotConfigured):
            telegram.send_message(111, "x")
