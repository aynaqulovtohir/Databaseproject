"""AI tahlili va chat: maxfiylik, ruxsatlar va navbat mantiqi testlari.

Haqiqiy AI chaqirilmaydi: Anthropic mijozi o'rniga soxta (mock) obyekt qo'yiladi.
"""
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from learning.models import Assignment
from submissions.models import Submission
from users.models import StudentGroup, User

from . import worker
from .client import AINotConfigured, AIPermanentError, AITransientError
from .models import AIAnalysis, ChatMessage
from .services import analyze_submission, chat_reply

PASSWORD = "Kuchli-Parol-2026"
SQL = "CREATE TABLE kitob (id SERIAL PRIMARY KEY, nomi VARCHAR(200) NOT NULL);"
GOOD_RESULT = {
    "summary": "Asosiy jadval bor, lekin bog'lanishlar yetishmaydi.",
    "issues": [{"title": "Tashqi kalit yo'q", "explanation": "Jadvallar bog'lanmagan.", "severity": "high"}],
    "recommendations": ["Mualliflar uchun alohida jadval haqida o'ylab ko'ring."],
    "suggested_score": 55,
    "score_rationale": "Mezonlardagi 4 jadvaldan faqat 1 tasi bor.",
}


def fake_response(text, stop_reason="end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=1200, output_tokens=800),
        stop_details=None,
    )


def fake_client(text=None, stop_reason="end_turn"):
    client = MagicMock()
    client.messages.create.return_value = fake_response(
        json.dumps(GOOD_RESULT) if text is None else text, stop_reason
    )
    return client


class DataMixin:
    @classmethod
    def setUpTestData(cls):
        cls.group_a = StudentGroup.objects.create(name="MAXFIY-GURUH-A")
        cls.group_b = StudentGroup.objects.create(name="B-guruh")
        cls.admin = User.objects.create_user("admin1", password=PASSWORD, role=User.Role.ADMIN)
        cls.teacher_a = User.objects.create_user(
            "teacher_a", password=PASSWORD, role=User.Role.TEACHER, first_name="Ustozismi"
        )
        cls.teacher_b = User.objects.create_user("teacher_b", password=PASSWORD, role=User.Role.TEACHER)
        cls.student = User.objects.create_user(
            "maxfiy_login",
            password=PASSWORD,
            role=User.Role.STUDENT,
            group=cls.group_a,
            first_name="Maxfiyism",
            last_name="Maxfiyfamiliya",
        )
        cls.classmate = User.objects.create_user(
            "classmate", password=PASSWORD, role=User.Role.STUDENT, group=cls.group_a
        )
        cls.outsider = User.objects.create_user(
            "outsider", password=PASSWORD, role=User.Role.STUDENT, group=cls.group_b
        )
        cls.group_a.teachers.add(cls.teacher_a)
        cls.assignment = Assignment.objects.create(
            title="Kutubxona bazasi",
            description="Kutubxona uchun baza loyihalang",
            grading_criteria="YASHIRIN-MEZON: kamida 4 ta jadval",
            author=cls.teacher_a,
            deadline=timezone.now() + timedelta(days=7),
        )
        cls.assignment.groups.add(cls.group_a)
        cls.submission = Submission.objects.create(
            assignment=cls.assignment, student=cls.student, sql_code=SQL, attempt_number=1
        )

    def setUp(self):
        cache.clear()


@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="test-key", AI_MODEL="claude-sonnet-5-5")
class AnalysisServiceTests(DataMixin, TestCase):
    def test_analysis_is_queued_for_every_new_submission(self):
        self.assertEqual(self.submission.analysis.status, AIAnalysis.Status.PENDING)

    def test_request_contains_no_personal_data(self):
        client = fake_client()
        with patch("ai.client.get_client", return_value=client):
            analyze_submission(self.submission)
        kwargs = client.messages.create.call_args.kwargs
        payload = json.dumps(kwargs, ensure_ascii=False, default=str)

        for secret in ("maxfiy_login", "Maxfiyism", "Maxfiyfamiliya", "MAXFIY-GURUH-A", "Ustozismi", "teacher_a"):
            self.assertNotIn(secret, payload)
        # Kerakli ma'lumot esa yuborilgan
        self.assertIn(SQL, payload)
        self.assertIn("Kutubxona uchun baza loyihalang", payload)
        self.assertIn("YASHIRIN-MEZON", payload)
        self.assertEqual(kwargs["model"], "claude-sonnet-5-5")
        self.assertEqual(kwargs["output_config"]["format"]["type"], "json_schema")

    def test_result_is_parsed(self):
        with patch("ai.client.get_client", return_value=fake_client()):
            result, input_tokens, output_tokens = analyze_submission(self.submission)
        self.assertEqual(result.suggested_score, 55)
        self.assertEqual(result.issues[0].severity, "high")
        self.assertEqual((input_tokens, output_tokens), (1200, 800))

    def test_score_is_clamped_to_0_100(self):
        for raw, expected in ((250, 100), (-5, 0)):
            text = json.dumps({**GOOD_RESULT, "suggested_score": raw})
            with patch("ai.client.get_client", return_value=fake_client(text)):
                result, _, _ = analyze_submission(self.submission)
            self.assertEqual(result.suggested_score, expected)

    def test_malformed_answer_is_permanent_error(self):
        for text in ("bu JSON emas", json.dumps({"summary": "faqat shu"}), "   "):
            with patch("ai.client.get_client", return_value=fake_client(text)):
                with self.assertRaises(AIPermanentError):
                    analyze_submission(self.submission)

    def test_refusal_and_truncation_are_permanent_errors(self):
        for stop_reason in ("refusal", "max_tokens"):
            with patch("ai.client.get_client", return_value=fake_client(stop_reason=stop_reason)):
                with self.assertRaises(AIPermanentError):
                    analyze_submission(self.submission)

    @override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="")
    def test_missing_key_raises_not_configured(self):
        with self.assertRaises(AINotConfigured):
            analyze_submission(self.submission)

    def test_sdk_errors_are_classified(self):
        import anthropic
        import httpx2

        request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

        def status_error(error_class, code):
            return error_class("xato", response=httpx2.Response(code, request=request), body=None)

        cases = [
            (anthropic.APIConnectionError(request=request), AITransientError),
            (status_error(anthropic.RateLimitError, 429), AITransientError),
            (status_error(anthropic.InternalServerError, 500), AITransientError),
            (status_error(anthropic.AuthenticationError, 401), AIPermanentError),
            (status_error(anthropic.BadRequestError, 400), AIPermanentError),
        ]
        for sdk_error, expected in cases:
            client = MagicMock()
            client.messages.create.side_effect = sdk_error
            with patch("ai.client.get_client", return_value=client):
                with self.assertRaises(expected, msg=type(sdk_error).__name__):
                    analyze_submission(self.submission)


@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="test-key")
class WorkerTests(DataMixin, TestCase):
    def test_empty_queue(self):
        AIAnalysis.objects.all().delete()
        self.assertFalse(worker.process_next())

    def test_success_saves_result(self):
        with patch("ai.client.get_client", return_value=fake_client()):
            self.assertTrue(worker.process_next())
        analysis = AIAnalysis.objects.get(submission=self.submission)
        self.assertEqual(analysis.status, AIAnalysis.Status.DONE)
        self.assertEqual(analysis.suggested_score, 55)
        self.assertEqual(analysis.issues[0]["title"], "Tashqi kalit yo'q")
        self.assertEqual(analysis.attempts, 1)
        self.assertEqual(analysis.input_tokens, 1200)
        self.assertIsNotNone(analysis.completed_at)

    def test_transient_error_is_retried_then_fails(self):
        with patch("ai.worker.analyze_submission", side_effect=AITransientError("tarmoq")):
            for expected_attempts in (1, 2):
                worker.process_next()
                analysis = AIAnalysis.objects.get(submission=self.submission)
                self.assertEqual(analysis.status, AIAnalysis.Status.PENDING)
                self.assertEqual(analysis.attempts, expected_attempts)
            worker.process_next()
        analysis.refresh_from_db()
        self.assertEqual(analysis.status, AIAnalysis.Status.FAILED)
        self.assertEqual(analysis.attempts, 3)
        self.assertEqual(analysis.error_message, "tarmoq")

    def test_permanent_error_fails_immediately(self):
        with patch("ai.worker.analyze_submission", side_effect=AIPermanentError("kalit noto'g'ri")):
            worker.process_next()
        analysis = AIAnalysis.objects.get(submission=self.submission)
        self.assertEqual(analysis.status, AIAnalysis.Status.FAILED)
        self.assertEqual(analysis.attempts, 1)

    def test_unexpected_error_does_not_crash_worker(self):
        with patch("ai.worker.analyze_submission", side_effect=RuntimeError("kutilmagan")):
            self.assertTrue(worker.process_next())
        self.assertEqual(AIAnalysis.objects.get(submission=self.submission).status, AIAnalysis.Status.FAILED)

    def test_oldest_first_and_processing_is_skipped(self):
        second = Submission.objects.create(
            assignment=self.assignment, student=self.student, sql_code=SQL, attempt_number=2
        )
        first_claimed = worker.claim_next_analysis()
        self.assertEqual(first_claimed.submission_id, self.submission.pk)
        self.assertEqual(worker.claim_next_analysis().submission_id, second.pk)
        self.assertIsNone(worker.claim_next_analysis())

    def test_stuck_analysis_is_released(self):
        AIAnalysis.objects.filter(submission=self.submission).update(
            status=AIAnalysis.Status.PROCESSING, started_at=timezone.now() - timedelta(minutes=30)
        )
        self.assertEqual(worker.release_stuck_analyses(), 1)
        self.assertEqual(AIAnalysis.objects.get(submission=self.submission).status, AIAnalysis.Status.PENDING)

    def test_recent_processing_is_not_released(self):
        AIAnalysis.objects.filter(submission=self.submission).update(
            status=AIAnalysis.Status.PROCESSING, started_at=timezone.now()
        )
        self.assertEqual(worker.release_stuck_analyses(), 0)


class ApiTestCase(DataMixin, APITestCase):
    def auth_as(self, user):
        response = self.client.post("/api/auth/login/", {"username": user.username, "password": PASSWORD})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


class AnalysisApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.url = f"/api/submissions/{self.submission.pk}/analysis/"
        AIAnalysis.objects.filter(submission=self.submission).update(
            status=AIAnalysis.Status.DONE,
            summary=GOOD_RESULT["summary"],
            issues=GOOD_RESULT["issues"],
            recommendations=GOOD_RESULT["recommendations"],
            suggested_score=55,
            score_rationale=GOOD_RESULT["score_rationale"],
        )

    def test_student_sees_feedback_without_score(self):
        self.auth_as(self.student)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "done")
        self.assertEqual(response.data["summary"], GOOD_RESULT["summary"])
        for hidden in ("suggested_score", "score_rationale", "error_message", "model_name"):
            self.assertNotIn(hidden, response.data)

    def test_teacher_and_admin_see_score(self):
        for user in (self.teacher_a, self.admin):
            self.auth_as(user)
            response = self.client.get(self.url)
            self.assertEqual(response.data["suggested_score"], 55, user.username)
            self.assertEqual(response.data["score_rationale"], GOOD_RESULT["score_rationale"])

    def test_others_cannot_see(self):
        for user in (self.classmate, self.outsider, self.teacher_b):
            self.auth_as(user)
            self.assertEqual(self.client.get(self.url).status_code, status.HTTP_404_NOT_FOUND, user.username)
        self.client.credentials()
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retry_only_for_failed_and_only_for_staff(self):
        retry_url = self.url + "retry/"
        self.auth_as(self.teacher_a)
        self.assertEqual(self.client.post(retry_url).status_code, status.HTTP_400_BAD_REQUEST)

        AIAnalysis.objects.filter(submission=self.submission).update(
            status=AIAnalysis.Status.FAILED, attempts=3, error_message="tarmoq"
        )
        self.auth_as(self.student)
        self.assertEqual(self.client.post(retry_url).status_code, status.HTTP_403_FORBIDDEN)
        self.auth_as(self.teacher_b)
        self.assertEqual(self.client.post(retry_url).status_code, status.HTTP_404_NOT_FOUND)

        self.auth_as(self.teacher_a)
        response = self.client.post(retry_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "pending")
        analysis = AIAnalysis.objects.get(submission=self.submission)
        self.assertEqual((analysis.attempts, analysis.error_message), (0, ""))

    def test_submitting_via_api_queues_analysis(self):
        self.auth_as(self.student)
        response = self.client.post(
            f"/api/assignments/{self.assignment.pk}/submissions/", {"sql_code": SQL}, format="json"
        )
        analysis = self.client.get(f"/api/submissions/{response.data['id']}/analysis/")
        self.assertEqual(analysis.data["status"], "pending")


@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="test-key", AI_CHAT_DAILY_LIMIT=3)
class ChatApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.url = f"/api/assignments/{self.assignment.pk}/chat/"

    def ask(self, content="Tashqi kalit nima?"):
        return self.client.post(self.url, {"content": content}, format="json")

    def test_student_asks_and_gets_answer(self):
        self.auth_as(self.student)
        with patch("ai.client.get_client", return_value=fake_client("Tashqi kalit - bu...")):
            response = self.ask()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["answer"]["content"], "Tashqi kalit - bu...")
        self.assertEqual(response.data["used_today"], 1)

        history = self.client.get(self.url).data
        self.assertEqual([m["role"] for m in history["messages"]], ["user", "assistant"])
        self.assertEqual(history["daily_limit"], 3)

    def test_request_has_no_personal_data_or_hidden_criteria(self):
        self.auth_as(self.student)
        client = fake_client("javob")
        with patch("ai.client.get_client", return_value=client):
            self.ask()
        payload = json.dumps(client.messages.create.call_args.kwargs, ensure_ascii=False, default=str)
        for secret in ("maxfiy_login", "Maxfiyism", "Maxfiyfamiliya", "MAXFIY-GURUH-A", "YASHIRIN-MEZON", "Ustozismi"):
            self.assertNotIn(secret, payload)
        self.assertIn("Kutubxona uchun baza loyihalang", payload)
        self.assertIn("Tashqi kalit nima?", payload)

    def test_history_is_sent_in_order(self):
        self.auth_as(self.student)
        client = fake_client("javob")
        with patch("ai.client.get_client", return_value=client):
            self.ask("birinchi savol")
            self.ask("ikkinchi savol")
        messages = client.messages.create.call_args.kwargs["messages"]
        self.assertEqual(
            [(m["role"], m["content"]) for m in messages],
            [("user", "birinchi savol"), ("assistant", "javob"), ("user", "ikkinchi savol")],
        )

    def test_daily_limit(self):
        self.auth_as(self.student)
        with patch("ai.client.get_client", return_value=fake_client("javob")):
            for _ in range(3):
                self.assertEqual(self.ask().status_code, status.HTTP_201_CREATED)
            self.assertEqual(self.ask().status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(ChatMessage.objects.filter(role="user").count(), 3)

    def test_yesterdays_messages_do_not_count(self):
        self.auth_as(self.student)
        for _ in range(3):
            message = ChatMessage.objects.create(
                assignment=self.assignment, student=self.student, role="user", content="kecha"
            )
            ChatMessage.objects.filter(pk=message.pk).update(created_at=timezone.now() - timedelta(days=1, hours=1))
        with patch("ai.client.get_client", return_value=fake_client("javob")):
            self.assertEqual(self.ask().status_code, status.HTTP_201_CREATED)

    def test_failed_ai_call_saves_nothing_and_keeps_limit(self):
        self.auth_as(self.student)
        with patch("ai.views.chat_reply", side_effect=AITransientError("tarmoq")):
            self.assertEqual(self.ask().status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        with patch("ai.views.chat_reply", side_effect=AIPermanentError("rad etildi")):
            self.assertEqual(self.ask().status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(ChatMessage.objects.count(), 0)

    @override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="")
    def test_not_configured(self):
        self.auth_as(self.student)
        response = self.ask()
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_validation(self):
        self.auth_as(self.student)
        with patch("ai.client.get_client", return_value=fake_client("javob")):
            self.assertEqual(self.ask("").status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(self.ask("x" * 4001).status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(self.client.post(self.url, {}, format="json").status_code, status.HTTP_400_BAD_REQUEST)

    def test_chat_is_private_to_the_student(self):
        ChatMessage.objects.create(
            assignment=self.assignment, student=self.student, role="user", content="mening savolim"
        )
        self.auth_as(self.classmate)
        self.assertEqual(self.client.get(self.url).data["messages"], [])
        for user in (self.teacher_a, self.admin):
            self.auth_as(user)
            self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN, user.username)
            self.assertEqual(self.ask().status_code, status.HTTP_403_FORBIDDEN)

    def test_other_group_student_and_anonymous_rejected(self):
        self.auth_as(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.ask().status_code, status.HTTP_404_NOT_FOUND)
        self.client.credentials()
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_classmates_history_is_not_sent_to_ai(self):
        ChatMessage.objects.create(
            assignment=self.assignment, student=self.classmate, role="user", content="SINFDOSH-SAVOLI"
        )
        self.auth_as(self.student)
        client = fake_client("javob")
        with patch("ai.client.get_client", return_value=client):
            self.ask()
        payload = json.dumps(client.messages.create.call_args.kwargs, ensure_ascii=False, default=str)
        self.assertNotIn("SINFDOSH-SAVOLI", payload)


@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="test-key")
class ChatServiceTests(DataMixin, TestCase):
    def test_chat_uses_low_effort_and_no_json_format(self):
        client = fake_client("javob")
        with patch("ai.client.get_client", return_value=client):
            self.assertEqual(chat_reply(self.assignment, [], "savol"), "javob")
        kwargs = client.messages.create.call_args.kwargs
        self.assertEqual(kwargs["output_config"], {"effort": "low"})


@override_settings(
    AI_PROVIDER="gemini", GEMINI_API_KEY="gemini-kalit", GEMINI_MODEL="gemini-sinov", GEMINI_FALLBACK_MODELS=[]
)
class GeminiProviderTests(DataMixin, TestCase):
    """AI_PROVIDER=gemini bo'lganda so'rov Google Gemini API'ga boradi."""

    @staticmethod
    def gemini_response(text="javob", status_code=200, finish_reason="STOP", body=None):
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = body or {
            "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": finish_reason}],
            "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 30, "thoughtsTokenCount": 10},
        }
        return response

    def test_analysis_request_and_result(self):
        with patch("ai.client.requests.post", return_value=self.gemini_response(json.dumps(GOOD_RESULT))) as post:
            result, input_tokens, output_tokens = analyze_submission(self.submission)
        self.assertEqual(result.suggested_score, 55)
        self.assertEqual((input_tokens, output_tokens), (120, 40))

        self.assertIn("gemini-sinov:generateContent", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["headers"], {"x-goog-api-key": "gemini-kalit"})
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["contents"][0]["role"], "user")
        self.assertIn(SQL, body["contents"][0]["parts"][0]["text"])
        config = body["generationConfig"]
        self.assertEqual(config["responseMimeType"], "application/json")
        self.assertEqual(config["responseSchema"]["type"], "OBJECT")
        self.assertNotIn("additionalProperties", json.dumps(config["responseSchema"]))
        # Shaxsiy ma'lumot Gemini'ga ham yuborilmaydi
        payload = json.dumps(body, ensure_ascii=False)
        for secret in ("maxfiy_login", "Maxfiyism", "Maxfiyfamiliya", "MAXFIY-GURUH-A"):
            self.assertNotIn(secret, payload)

    def test_chat_history_roles_are_converted(self):
        from .services import chat_reply

        history = [{"role": "user", "content": "savol"}, {"role": "assistant", "content": "javob"}]
        with patch("ai.client.requests.post", return_value=self.gemini_response("yangi javob")) as post:
            self.assertEqual(chat_reply(self.assignment, history, "yana savol"), "yangi javob")
        roles = [item["role"] for item in post.call_args.kwargs["json"]["contents"]]
        self.assertEqual(roles, ["user", "model", "user"])
        self.assertNotIn("responseSchema", post.call_args.kwargs["json"]["generationConfig"])

    def test_errors_are_classified(self):
        import requests

        from .client import create_message

        invalid_key = self.gemini_response(status_code=400, body={"error": {"message": "API key not valid."}})
        cases = [
            (self.gemini_response(status_code=429), AITransientError),
            (self.gemini_response(status_code=503), AITransientError),
            (self.gemini_response(status_code=404), AIPermanentError),
            (invalid_key, AIPermanentError),
            (self.gemini_response(finish_reason="MAX_TOKENS"), AIPermanentError),
            (self.gemini_response(body={"promptFeedback": {"blockReason": "SAFETY"}}), AIPermanentError),
        ]
        for response, expected in cases:
            with patch("ai.client.requests.post", return_value=response), self.assertRaises(expected):
                create_message(max_tokens=100, system="s", messages=[{"role": "user", "content": "x"}])
        with patch("ai.client.requests.post", side_effect=requests.ConnectionError()):
            with self.assertRaises(AITransientError):
                create_message(max_tokens=100, system="s", messages=[{"role": "user", "content": "x"}])

    @override_settings(GEMINI_FALLBACK_MODELS=["zaxira-1", "gemini-sinov", "zaxira-2"])
    def test_busy_model_falls_back_to_next(self):
        from .client import create_message, extract_text

        busy = self.gemini_response(status_code=503)
        with patch("ai.client.requests.post", side_effect=[busy, busy, self.gemini_response("zaxira javob")]) as post:
            response = create_message(max_tokens=100, system="s", messages=[{"role": "user", "content": "x"}])
        self.assertEqual(extract_text(response), "zaxira javob")
        # Asosiy model takroran sinalmaydi
        urls = [call.args[0] for call in post.call_args_list]
        self.assertEqual([url.split("models/")[1].split(":")[0] for url in urls], ["gemini-sinov", "zaxira-1", "zaxira-2"])

    @override_settings(GEMINI_FALLBACK_MODELS=["zaxira-1"])
    def test_all_models_busy_is_transient(self):
        import requests

        from .client import create_message

        with patch("ai.client.requests.post", side_effect=[requests.Timeout(), self.gemini_response(status_code=503)]):
            with self.assertRaises(AITransientError):
                create_message(max_tokens=100, system="s", messages=[{"role": "user", "content": "x"}])

    @override_settings(GEMINI_FALLBACK_MODELS=["zaxira-1"])
    def test_bad_key_does_not_fall_back(self):
        from .client import create_message

        with patch("ai.client.requests.post", return_value=self.gemini_response(status_code=403)) as post:
            with self.assertRaises(AIPermanentError):
                create_message(max_tokens=100, system="s", messages=[{"role": "user", "content": "x"}])
        self.assertEqual(post.call_count, 1)

    @override_settings(GEMINI_API_KEY="")
    def test_not_configured_without_gemini_key(self):
        from .client import AINotConfigured, create_message, is_configured

        self.assertFalse(is_configured())
        with self.assertRaises(AINotConfigured):
            create_message(max_tokens=100, system="s", messages=[])

    def test_worker_records_gemini_model(self):
        with patch("ai.client.requests.post", return_value=self.gemini_response(json.dumps(GOOD_RESULT))):
            self.assertTrue(worker.process_next())
        self.assertEqual(AIAnalysis.objects.get(submission=self.submission).model_name, "gemini-sinov")


@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="test-key")
class AIUsageTests(DataMixin, APITestCase):
    """Har bir AI so'rovi hisobga olinadi; hisobotni faqat admin ko'radi."""

    def auth_as(self, user):
        cache.clear()
        response = self.client.post("/api/auth/login/", {"username": user.username, "password": PASSWORD})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_successful_and_failed_requests_are_recorded_without_personal_data(self):
        from .models import AIUsage

        with patch("ai.client.get_client", return_value=fake_client()):
            analyze_submission(self.submission)
        with patch("ai.client.get_client", return_value=fake_client(stop_reason="refusal")):
            with self.assertRaises(AIPermanentError):
                chat_reply(self.assignment, [], "Savol")
        ok, failed = AIUsage.objects.order_by("id")
        self.assertEqual((ok.purpose, ok.ok, ok.input_tokens, ok.output_tokens), ("analysis", True, 1200, 800))
        self.assertEqual((failed.purpose, failed.ok), ("chat", False))
        self.assertIn("AIPermanentError", failed.error)
        stored = " ".join(str(value) for value in AIUsage.objects.values_list("model_name", "error"))
        for secret in ("maxfiy_login", "Maxfiyism", SQL[:20], "Savol"):
            self.assertNotIn(secret, stored)

    @override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="")
    def test_not_configured_is_not_recorded(self):
        from .models import AIUsage

        with self.assertRaises(AINotConfigured):
            analyze_submission(self.submission)
        self.assertFalse(AIUsage.objects.exists())

    def test_recording_failure_does_not_break_answer(self):
        with patch("ai.models.AIUsage.objects.create", side_effect=RuntimeError("baza band")):
            with patch("ai.client.get_client", return_value=fake_client()):
                result, _, _ = analyze_submission(self.submission)
        self.assertEqual(result.suggested_score, 55)

    @override_settings(AI_PRICE_INPUT_PER_MTOK=1.0, AI_PRICE_OUTPUT_PER_MTOK=4.0)
    def test_report_for_admin_only(self):
        from .models import AIUsage

        AIUsage.objects.create(purpose="lab_advice", model_name="m1", input_tokens=500_000, output_tokens=250_000)
        AIUsage.objects.create(purpose="lab_advice", model_name="m1", ok=False, error="x")
        old = AIUsage.objects.create(purpose="chat", input_tokens=10, output_tokens=10)
        AIUsage.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=400))

        self.auth_as(self.teacher_a)
        self.assertEqual(self.client.get("/api/ai/usage/").status_code, status.HTTP_403_FORBIDDEN)
        self.auth_as(self.student)
        self.assertEqual(self.client.get("/api/ai/usage/").status_code, status.HTTP_403_FORBIDDEN)

        self.auth_as(self.admin)
        for bad in ("0", "366", "abc", "-1"):
            self.assertEqual(self.client.get("/api/ai/usage/", {"days": bad}).status_code, 400)
        data = self.client.get("/api/ai/usage/", {"days": 7}).data
        self.assertEqual(len(data["daily"]), 7)
        self.assertEqual(
            data["period"],
            {"requests": 2, "failed": 1, "input_tokens": 500_000, "output_tokens": 250_000, "cache_read_tokens": 0, "cost": 1.5},
        )
        self.assertEqual(data["today"]["requests"], 2)
        self.assertEqual(data["by_purpose"][0]["label"], "SQL maslahati")
        self.assertTrue(data["price"]["configured"])
        self.assertEqual(data["daily"][-1]["requests"], 2)


@override_settings(
    AI_PROVIDER="anthropic",
    ANTHROPIC_API_KEY="test-key",
    AI_MODEL="asosiy-model",
    AI_FAST_MODEL="tez-model",
    AI_PRICE_INPUT_PER_MTOK=2.0,
    AI_PRICE_OUTPUT_PER_MTOK=10.0,
    AI_FAST_PRICE_INPUT_PER_MTOK=0.1,
    AI_FAST_PRICE_OUTPUT_PER_MTOK=0.5,
)
class CachingAndFastModelTests(DataMixin, TestCase):
    """Tizim ko'rsatmasi keshlanadi; maslahatlar arzon modelda; xarajat kesh va model narxi bo'yicha hisoblanadi."""

    def test_system_prompt_is_cached_and_main_model_used(self):
        client = fake_client("javob")
        with patch("ai.client.get_client", return_value=client):
            chat_reply(self.assignment, [], "NOYOB-SAVOL-42")
        kwargs = client.messages.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "asosiy-model")
        self.assertEqual(kwargs["system"][-1]["cache_control"], {"type": "ephemeral"})
        # O'zgaruvchan savol keshlanadigan qismdan keyin keladi
        self.assertNotIn("NOYOB-SAVOL-42", json.dumps(kwargs["system"], ensure_ascii=False))

    def test_fast_model_and_cost_with_cache(self):
        from .client import create_message
        from .models import AIUsage

        client = fake_client("javob")
        client.messages.create.return_value.usage = SimpleNamespace(
            input_tokens=1_000_000, output_tokens=1_000_000, cache_read_input_tokens=1_000_000, cache_creation_input_tokens=0
        )
        with patch("ai.client.get_client", return_value=client):
            create_message(purpose="lab_advice", fast=True, max_tokens=10, system="s", messages=[])
        self.assertEqual(client.messages.create.call_args.kwargs["model"], "tez-model")
        usage = AIUsage.objects.get()
        self.assertEqual((usage.model_name, usage.cache_read_tokens), ("tez-model", 1_000_000))
        # 0.1 (kirish) + 0.01 (kesh: 0.1 narxning 10%) + 0.5 (chiqish)
        self.assertAlmostEqual(usage.cost, 0.61)

    @override_settings(AI_FAST_MODEL="")
    def test_empty_fast_model_falls_back_to_main(self):
        from .client import create_message

        client = fake_client("javob")
        with patch("ai.client.get_client", return_value=client):
            create_message(purpose="lab_advice", fast=True, max_tokens=10, system="s", messages=[])
        self.assertEqual(client.messages.create.call_args.kwargs["model"], "asosiy-model")
