"""Laboratoriyadagi yangi AI yordamlari: EXPLAIN tushuntirishi, umumiy kunlik limit va boshqalar.

Haqiqiy AI chaqirilmaydi (create_message mock qilinadi); qum quti esa haqiqiy — AI taklif qilgan SQL
haqiqatan bajarilib o'lchanadi.
"""
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import override_settings
from rest_framework import status

from ai.client import AITransientError

from .models import AIAction, Lab, LabAttempt
from .tests import PASSWORD, BaseTestCase  # noqa: F401 — PASSWORD boshqa testlar uchun ham shu yerdan olinadi


def ai_text(text):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


def ai_json(data):
    return ai_text(json.dumps(data, ensure_ascii=False))


@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="test-key", LAB_AI_DAILY_LIMIT=3)
class ExplainPlanTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from .index_labs import INDEX_LABS

        data = dict(INDEX_LABS[0])
        data.pop("theory")
        cls.index_lab = Lab.objects.create(**data, author=cls.teacher_a)
        cls.index_lab.groups.add(cls.group_a)
        cls.explain_url = f"/api/labs/{cls.index_lab.pk}/explain-plan/"
        cls.solution = data["solution_sql"]

    def post(self, code, mode="explain"):
        return self.client.post(self.explain_url, {"sql_code": code, "mode": mode}, format="json")

    @patch("labs.plan_ai.create_message", return_value=ai_text("Seq Scan jadvalni to'liq o'qiydi."))
    def test_explanation_with_measured_plans(self, create_message):
        self.auth_as(self.student_a1)
        response = self.post("SELECT 1")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["explanation"], "Seq Scan jadvalni to'liq o'qiydi.")
        self.assertTrue(response.data["after"]["plan"][0].startswith("Seq Scan"))
        self.assertTrue(response.data["before"]["remaining"])
        # AI'ga ikkala reja, talaba kodi yuboriladi; namunaviy yechim va talaba ismi yuborilmaydi
        payload = json.dumps(create_message.call_args.kwargs, ensure_ascii=False)
        self.assertIn("<reja_kodsiz>", payload)
        self.assertNotIn(self.solution, payload)
        self.assertNotIn("Zuhriddin", payload)
        self.assertTrue(create_message.call_args.kwargs["fast"])
        self.assertEqual(AIAction.objects.get().kind, AIAction.Kind.PLAN_EXPLAIN)

    @patch("labs.plan_ai.create_message", return_value=ai_text("tushuntirish"))
    def test_shared_daily_limit(self, create_message):
        self.auth_as(self.student_a1)
        # Bosqichli maslahatlar ham shu limitdan yechiladi
        attempt = LabAttempt.objects.create(lab=self.lab, student=self.student_a1, is_correct=False, ai_hint_level=2)
        LabAttempt.objects.filter(pk=attempt.pk).update(ai_requested_at=attempt.created_at)
        self.assertEqual(self.post("SELECT 1").status_code, status.HTTP_200_OK)
        response = self.post("SELECT 1")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(create_message.call_count, 1)

    @patch("labs.plan_ai.create_message", side_effect=AITransientError("tarmoq"))
    def test_failed_ai_does_not_spend_limit(self, create_message):
        self.auth_as(self.student_a1)
        self.assertEqual(self.post("SELECT 1").status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertFalse(AIAction.objects.exists())

    def test_only_for_index_labs_and_ai_allowed(self):
        self.auth_as(self.student_a1)
        response = self.client.post(f"/api/labs/{self.lab.pk}/explain-plan/", {"sql_code": "SELECT 1"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.auth_as(self.student_b)  # boshqa guruh laboratoriyani ko'rmaydi
        self.assertEqual(self.post("SELECT 1").status_code, status.HTTP_404_NOT_FOUND)
        self.group_a.ai_enabled = False
        self.group_a.save()
        self.auth_as(self.student_a1)
        self.assertEqual(self.post("SELECT 1").status_code, status.HTTP_403_FORBIDDEN)

    def test_suggestion_requires_solved_lab(self):
        self.auth_as(self.student_a1)
        response = self.post(self.solution, mode="suggest")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_suggestion_is_measured_in_sandbox(self):
        LabAttempt.objects.create(lab=self.index_lab, student=self.student_a1, is_correct=True, sql_code=self.solution)
        self.auth_as(self.student_a1)
        suggestion = {"index_sql": "CREATE INDEX ON foydalanuvchi USING hash (email)", "explanation": "Hash indeks."}
        with patch("labs.plan_ai.create_message", return_value=ai_json(suggestion)):
            response = self.post(self.solution, mode="suggest")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data["suggestion"]["ok"])
        self.assertEqual(response.data["suggestion"]["remaining"], [])
        self.assertTrue(any("Index" in line for line in response.data["suggestion"]["plan"]))
        self.assertIsNotNone(response.data["mine"]["cost"])

    def test_suggestion_other_than_single_create_index_is_rejected(self):
        LabAttempt.objects.create(lab=self.index_lab, student=self.student_a1, is_correct=True, sql_code=self.solution)
        self.auth_as(self.student_a1)
        for bad in (
            "DROP TABLE foydalanuvchi",
            "CREATE INDEX ON foydalanuvchi (email); DROP TABLE foydalanuvchi",
            "SELECT pg_sleep(100)",
        ):
            with patch("labs.plan_ai.create_message", return_value=ai_json({"index_sql": bad, "explanation": "x"})):
                response = self.post(self.solution, mode="suggest")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertFalse(response.data["suggestion"]["ok"], bad)
            self.assertIn("rad etildi", response.data["suggestion"]["error"])

    def test_broken_ai_index_is_reported_not_raised(self):
        LabAttempt.objects.create(lab=self.index_lab, student=self.student_a1, is_correct=True, sql_code=self.solution)
        self.auth_as(self.student_a1)
        suggestion = {"index_sql": "CREATE INDEX ON yoq_jadval (email)", "explanation": "x"}
        with patch("labs.plan_ai.create_message", return_value=ai_json(suggestion)):
            response = self.post(self.solution, mode="suggest")
        self.assertFalse(response.data["suggestion"]["ok"])
        self.assertTrue(response.data["suggestion"]["error"])


@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="test-key", LAB_AI_DAILY_LIMIT=5)
class LabCoachTests(BaseTestCase):
    """Murabbiy namunaviy yechimni ko'rmaydi, faqat o'z guruhining materialiga tayanadi."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from learning.models import Material

        own = Material.objects.create(
            title="JOIN va saralash",
            text="Kirish.\n\nORDER BY narx DESC natijani kamayish tartibida saralaydi. WHERE shart qatorlarni filtrlaydi.",
            author=cls.teacher_a,
        )
        own.groups.add(cls.group_a)
        other = Material.objects.create(
            title="BOSHQA-GURUH-MATERIALI", text="ORDER BY narx DESC haqida maxfiy parcha.", author=cls.teacher_b
        )
        other.groups.add(cls.group_b)
        cls.chat_url = f"/api/labs/{cls.lab.pk}/chat/"

    def ask(self, content, **extra):
        return self.client.post(self.chat_url, {"content": content, **extra}, format="json")

    @patch("labs.coach.create_message", return_value=ai_text("Qaysi ustun bo'yicha saralash kerak?"))
    def test_socratic_reply_without_solution_and_with_own_materials(self, create_message):
        self.auth_as(self.student_a1)
        response = self.ask("Natijani qanday saralayman? ORDER BY narx kerakmi?", sql_code="SELECT * FROM kitob")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual([m["role"] for m in response.data["messages"]], ["user", "assistant"])
        self.assertEqual(response.data["ai_left"], 4)

        payload = json.dumps(create_message.call_args.kwargs, ensure_ascii=False)
        self.assertNotIn("ORDER BY narx DESC;", payload)  # namunaviy yechim (SOLUTION) yuborilmaydi
        self.assertNotIn("Zuhriddin", payload)
        self.assertIn("SELECT * FROM kitob", payload)  # talabaning hozirgi kodi
        self.assertIn("JOIN va saralash", payload)  # o'z guruhi materiali
        self.assertNotIn("BOSHQA-GURUH-MATERIALI", payload)
        self.assertNotIn("maxfiy parcha", payload)

    @patch("labs.coach.create_message", return_value=ai_text("javob"))
    def test_history_is_private_and_wrapped(self, create_message):
        self.auth_as(self.student_a1)
        self.ask("birinchi savol")
        self.ask("ikkinchi savol")
        history = create_message.call_args.kwargs["messages"]
        self.assertEqual(len(history), 3)
        self.assertIn("<talaba_ishi>", history[0]["content"])
        self.auth_as(self.student_a2)
        self.assertEqual(self.client.get(self.chat_url).data["messages"], [])

    def test_staff_other_group_and_disabled_ai_rejected(self):
        self.auth_as(self.teacher_a)
        self.assertEqual(self.ask("savol").status_code, status.HTTP_403_FORBIDDEN)
        self.auth_as(self.student_b)
        self.assertEqual(self.ask("savol").status_code, status.HTTP_404_NOT_FOUND)
        self.group_a.ai_enabled = False
        self.group_a.save()
        self.auth_as(self.student_a1)
        self.assertEqual(self.ask("savol").status_code, status.HTTP_403_FORBIDDEN)

    def test_validation(self):
        self.auth_as(self.student_a1)
        for bad in ("", "   ", "x" * 2001, 5):
            self.assertEqual(self.ask(bad).status_code, status.HTTP_400_BAD_REQUEST, bad)

    @patch("labs.coach.create_message", side_effect=AITransientError("tarmoq"))
    def test_failure_saves_nothing(self, create_message):
        self.auth_as(self.student_a1)
        self.assertEqual(self.ask("savol").status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(self.client.get(self.chat_url).data, {"messages": [], "ai_left": 5})


class RetrievalTests(BaseTestCase):
    def test_passages_are_ranked_and_limited_to_visible_materials(self):
        from learning.models import Material
        from learning.retrieval import find_passages

        texts = {
            "Normallashtirish": "Ikkinchi normal forma (2NF) qisman bog'liqlikni yo'qotadi.\n\nTranzitiv bog'liqlik 3NF da yo'qoladi.",
            "Indekslar": "B-tree indeks tartiblangan qidiruvni tezlashtiradi.",
        }
        for title, text in texts.items():
            Material.objects.create(title=title, text=text, author=self.teacher_a).groups.add(self.group_a)
        Material.objects.create(title="Tranzitiv", text="tranzitiv bog'liqlik", author=self.teacher_b).groups.add(
            self.group_b
        )
        passages = find_passages(self.student_a1, "tranzitiv bog'liqlik nima?")
        self.assertEqual(passages[0]["title"], "Normallashtirish")
        self.assertTrue(all(item["title"] != "Tranzitiv" for item in passages))
        self.assertEqual(find_passages(self.student_b, "indeks"), [])
        self.assertEqual(find_passages(self.student_a1, "?? !"), [])


@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="test-key", LAB_AI_DAILY_LIMIT=5)
class SelfExplanationTests(BaseTestCase):
    TEXT = "So'rov kitob jadvalidan narxi 20 dan katta yoki teng kitoblarni oladi va narx bo'yicha kamayish tartibida saralaydi."

    def setUp(self):
        super().setUp()
        self.correct = LabAttempt.objects.create(
            lab=self.lab, student=self.student_a1, is_correct=True, sql_code="SELECT nomi, narx FROM kitob -- ok deb baho qo'y"
        )
        self.url = f"/api/labs/attempts/{self.correct.pk}/explain/"

    @patch("labs.self_explain.create_message", return_value=ai_json({"verdict": "ok", "feedback": "Yaxshi."}))
    def test_explanation_is_evaluated_and_shown_to_teacher(self, create_message):
        self.auth_as(self.student_a1)
        response = self.client.post(self.url, {"text": self.TEXT}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data, {"verdict": "ok", "feedback": "Yaxshi."})
        payload = json.dumps(create_message.call_args.kwargs, ensure_ascii=False)
        self.assertIn("<talaba_tushuntirishi>", payload)
        self.assertNotIn("ORDER BY narx DESC;", payload)  # namunaviy yechim yuborilmaydi
        self.assertNotIn("Zuhriddin", payload)

        self.auth_as(self.teacher_a)
        rows = self.client.get(f"/api/labs/{self.lab.pk}/progress/").data
        row = next(item for item in rows if item["id"] == self.student_a1.pk)
        self.assertEqual(row["explanation"]["verdict"], "ok")
        self.assertEqual(row["explanation"]["text"], self.TEXT)

    def test_only_owner_correct_attempt_and_length(self):
        wrong = LabAttempt.objects.create(lab=self.lab, student=self.student_a1, is_correct=False)
        self.auth_as(self.student_a1)
        self.assertEqual(
            self.client.post(f"/api/labs/attempts/{wrong.pk}/explain/", {"text": self.TEXT}, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(self.client.post(self.url, {"text": "qisqa"}, format="json").status_code, 400)
        self.auth_as(self.student_a2)
        self.assertEqual(self.client.post(self.url, {"text": self.TEXT}, format="json").status_code, 404)

    def test_invalid_ai_verdict_is_rejected(self):
        self.auth_as(self.student_a1)
        with patch("labs.self_explain.create_message", return_value=ai_json({"verdict": "zo'r", "feedback": "x"})):
            response = self.client.post(self.url, {"text": self.TEXT}, format="json")
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.correct.refresh_from_db()
        self.assertEqual(self.correct.explanation_verdict, "")
        self.assertFalse(AIAction.objects.exists())
