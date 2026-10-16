"""Talablarni aniqlash: AI-buyurtmachi bilan suhbat. Haqiqiy AI chaqirilmaydi (create_message mock qilinadi)."""
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework import status

from .er import normalize
from .interview import RequirementsError, coverage, validate_requirements
from .interview_labs import INTERVIEW_LABS
from .models import InterviewMessage, Lab, LabAttempt
from .tests import BaseTestCase
from .tests_ai import ai_json


class InterviewDataTests(SimpleTestCase):
    def test_every_reference_name_is_said_in_requirements(self):
        """Talaba diagrammadagi nomlarni faqat buyurtmachidan bilib oladi: har bir nom talablarda aytilgan bo'lsin."""
        for lab in INTERVIEW_LABS:
            text = normalize(" ".join(item["text"] for item in lab["requirements"]))
            validate_requirements(lab["requirements"])
            for entity in lab["reference_diagram"]["entities"]:
                self.assertIn(normalize(entity["name"]), text, lab["title"])
                for attribute in entity["attributes"]:
                    self.assertIn(normalize(attribute["name"]), text, f"{lab['title']}: {attribute['name']}")

    def test_validation(self):
        with self.assertRaises(RequirementsError):
            validate_requirements([{"id": "R1", "text": "a", "kind": "entity"}, {"id": "R1", "text": "b", "kind": "rule"}])
        with self.assertRaises(RequirementsError):
            validate_requirements([{"id": "R1", "text": "a", "kind": "boshqa"}])
        with self.assertRaises(RequirementsError):
            validate_requirements([{"id": "R 1", "text": "a", "kind": "rule"}])
        self.assertEqual(validate_requirements([{"id": "R1", "text": "  a   b ", "kind": "rule"}]), [{"id": "R1", "text": "a b", "kind": "rule"}])


@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="test-key", LAB_INTERVIEW_QUESTION_LIMIT=3)
class InterviewApiTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        data = dict(INTERVIEW_LABS[0])
        cls.interview_lab = Lab.objects.create(**data, author=cls.teacher_a)
        cls.interview_lab.groups.add(cls.group_a, cls.group_b)
        cls.url = f"/api/labs/{cls.interview_lab.pk}/interview/"
        cls.group_b.ai_enabled = False
        cls.group_b.save()

    def ask(self, content="Kimlar haqida ma'lumot saqlanadi?", revealed=("R1",), text=None):
        # Odatda javob belgilangan talablar mazmunini aytadi (server buni matn bo'yicha tekshiradi)
        texts = {item["id"]: item["text"] for item in INTERVIEW_LABS[0]["requirements"]}
        text = text if text is not None else " ".join(texts.get(item, "") for item in revealed) or "Yaxshi savol."
        reply = ai_json({"reply": text, "revealed": list(revealed)})
        with patch("labs.interview.create_message", return_value=reply) as mock:
            response = self.client.post(self.url, {"content": content}, format="json")
        return response, mock

    def test_requirements_are_hidden_from_ai_group_and_given_to_control_group(self):
        self.auth_as(self.student_a1)
        interview = self.client.get(f"/api/labs/{self.interview_lab.pk}/").data["interview"]
        self.assertEqual(interview, {"total": 12, "ai": True, "requirements": None})
        self.auth_as(self.student_b)
        interview = self.client.get(f"/api/labs/{self.interview_lab.pk}/").data["interview"]
        self.assertFalse(interview["ai"])
        self.assertEqual(len(interview["requirements"]), 12)
        # Oddiy ER laboratoriyasida suhbat yo'q
        self.auth_as(self.student_a1)
        self.assertIsNone(self.client.get(f"/api/labs/{self.lab.pk}/").data["interview"])

    def test_question_records_only_known_revealed_requirements(self):
        self.auth_as(self.student_a1)
        response, mock = self.ask(revealed=("R1", "R2"))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual([item["id"] for item in response.data["found"]], ["R1", "R2"])
        self.assertEqual(response.data["total"], 12)
        self.assertIsNone(response.data["missed"])  # yechilmaguncha aniqlanmagan talablar ko'rsatilmaydi
        self.assertEqual(response.data["questions_left"], 2)
        # Savol teg ichida yuboriladi; AI namunaviy diagrammani ko'rmaydi, javob sxemasida faqat ma'lum id'lar
        params = mock.call_args.kwargs
        self.assertIn("<talaba_savoli>", params["messages"][-1]["content"])
        self.assertNotIn('"entities"', str(params))
        self.assertNotIn('"source_card"', str(params))
        self.assertEqual(params["output_config"]["format"]["schema"]["properties"]["revealed"]["items"]["enum"][:2], ["R1", "R2"])

    def test_unknown_ids_from_ai_are_dropped(self):
        self.auth_as(self.student_a1)
        response, _ = self.ask(revealed=("R99", "R3"))
        self.assertEqual([item["id"] for item in response.data["found"]], ["R3"])
        self.assertEqual(InterviewMessage.objects.get(role="assistant").revealed, ["R3"])

    def test_marked_but_unsaid_requirement_is_not_counted(self):
        """AI ba'zan aytmagan talabni ham belgilaydi: u javob matnida bo'lmasa, hisobga olinmaydi."""
        self.auth_as(self.student_a1)
        response, _ = self.ask(
            revealed=("R4", "R7"),
            text="Har bir shifokor faqat bitta bo'limda ishlaydi, bitta bo'limda esa bir nechta shifokor ishlaydi.",
        )
        self.assertEqual([item["id"] for item in response.data["found"]], ["R7"])

    def test_missed_requirements_are_shown_after_solving(self):
        self.auth_as(self.student_a1)
        self.ask(revealed=("R1",))
        LabAttempt.objects.create(lab=self.interview_lab, student=self.student_a1, diagram={}, is_correct=True)
        data = self.client.get(self.url).data
        self.assertEqual(len(data["missed"]), 11)

    def test_question_limit(self):
        self.auth_as(self.student_a1)
        for _ in range(3):
            self.assertEqual(self.ask()[0].status_code, status.HTTP_201_CREATED)
        response, mock = self.ask()
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        mock.assert_not_called()

    def test_access(self):
        self.auth_as(self.student_b)  # nazorat guruhi
        self.assertEqual(self.ask()[0].status_code, status.HTTP_403_FORBIDDEN)
        self.auth_as(self.teacher_a)
        self.assertEqual(self.ask()[0].status_code, status.HTTP_403_FORBIDDEN)
        self.auth_as(self.student_a1)
        self.url = f"/api/labs/{self.lab.pk}/interview/"  # suhbatsiz laboratoriya
        self.assertEqual(self.ask()[0].status_code, status.HTTP_403_FORBIDDEN)

    def test_messages_are_private(self):
        self.auth_as(self.student_a1)
        self.ask()
        self.auth_as(self.student_a2)
        self.assertEqual(self.client.get(self.url).data["messages"], [])

    def test_staff_serializer_validates_and_clears_requirements(self):
        self.auth_as(self.teacher_a)
        lab = INTERVIEW_LABS[0]
        bad = self.client.post(
            "/api/labs/",
            {"kind": "er", "title": "X", "description": "x", "reference_diagram": lab["reference_diagram"],
             "requirements": [{"id": "R1", "text": "a", "kind": "noma'lum"}], "groups": [self.group_a.pk]},
            format="json",
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("requirements", bad.data)
        response = self.client.get(f"/api/labs/{self.interview_lab.pk}/")
        self.assertEqual(len(response.data["requirements"]), 12)  # o'qituvchi talablarni ko'radi

    def test_coverage(self):
        message = InterviewMessage(lab=self.interview_lab, student=self.student_a1, role="assistant", revealed=["R1", "R2", "R3"])
        self.assertEqual(coverage(self.interview_lab, [message]), 25.0)
