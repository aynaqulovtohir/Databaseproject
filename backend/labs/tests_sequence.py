"""Modullar: tartib, ketma-ket ochilish (qulf serverda), modullarni boshqarish va qiynalgan talabaga tavsiya."""
import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from ai.client import AITransientError
from users.models import StudentGroup, User

from .models import AIAction, Lab, LabAttempt, LabModule, StudyAdvice
from .sequence import lock_map
from .study_advice import MIN_WRONG

WRONG_FEEDBACK = {"error": {"sqlstate": "42703", "message": "column \"nom\" does not exist", "tip": "Ustun nomini tekshiring."}}


def fake_ai_response(content):
    return type("Response", (), {"content": [type("Block", (), {"type": "text", "text": json.dumps(content)})()]})()


class SequenceTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.group = StudentGroup.objects.create(name="S-guruh", ai_enabled=True)
        cls.control = StudentGroup.objects.create(name="S-nazorat", ai_enabled=False)
        cls.teacher = User.objects.create_user("s_teacher", role=User.Role.TEACHER)
        cls.other_teacher = User.objects.create_user("s_teacher2", role=User.Role.TEACHER)
        cls.group.teachers.add(cls.teacher)
        cls.control.teachers.add(cls.teacher)
        cls.student = User.objects.create_user("s_student", role=User.Role.STUDENT, group=cls.group)
        cls.control_student = User.objects.create_user("s_control", role=User.Role.STUDENT, group=cls.control)
        cls.module1 = LabModule.objects.create(title="1-modul", order=1, author=cls.teacher)
        cls.module2 = LabModule.objects.create(title="2-modul", order=2, author=cls.teacher)
        cls.free_module = LabModule.objects.create(title="Erkin", order=3, sequential=False, author=cls.teacher)

        def lab(title, module=None, position=0, level=None):
            item = Lab.objects.create(
                title=title, description=f"{title} sharti", setup_sql="", solution_sql="SELECT 1;", author=cls.teacher,
                module=module, position=position, level=level,
            )
            item.groups.add(cls.group, cls.control)
            return item

        # Bazadagi tartib ataylab aralash: tartibni position belgilaydi
        cls.lab2 = lab("Murakkabroq", cls.module1, 2, 3)
        cls.lab1 = lab("Sodda", cls.module1, 1, 1)
        cls.lab3 = lab("2-modul boshi", cls.module2, 1, 4)
        cls.free = lab("Modulsiz")
        cls.free_in_module = lab("Erkin moduldagi", cls.free_module, 1)

    def setUp(self):
        cache.clear()

    def attempt(self, lab, correct, student=None):
        return LabAttempt.objects.create(
            lab=lab, student=student or self.student, sql_code="SELECT nom FROM t;", is_correct=correct,
            feedback={} if correct else WRONG_FEEDBACK,
        )

    def locks(self, student=None):
        return {lab_id: (blocker.pk if blocker else None) for lab_id, blocker in lock_map(student or self.student, Lab.objects.select_related("module")).items()}

    def test_chain_follows_module_and_position_order(self):
        locks = self.locks()
        self.assertIsNone(locks[self.lab1.pk])
        self.assertEqual(locks[self.lab2.pk], self.lab1.pk)
        self.assertEqual(locks[self.lab3.pk], self.lab1.pk)
        self.assertIsNone(locks[self.free.pk])
        self.assertIsNone(locks[self.free_in_module.pk])

        self.attempt(self.lab1, False)
        self.assertEqual(self.locks()[self.lab2.pk], self.lab1.pk)  # noto'g'ri urinish ochmaydi
        self.attempt(self.lab1, True)
        locks = self.locks()
        self.assertIsNone(locks[self.lab2.pk])
        self.assertEqual(locks[self.lab3.pk], self.lab2.pk)
        self.attempt(self.lab2, True)
        self.assertIsNone(self.locks()[self.lab3.pk])

    def test_locked_lab_is_closed_on_server(self):
        self.client.force_authenticate(self.student)
        rows = {row["id"]: row for row in self.client.get("/api/labs/").data}
        self.assertTrue(rows[self.lab2.pk]["locked"])
        self.assertEqual(rows[self.lab2.pk]["blocked_by"], {"id": self.lab1.pk, "title": "Sodda"})
        self.assertEqual(rows[self.lab2.pk]["description"], "")  # shart ko'rsatilmaydi
        self.assertEqual(rows[self.lab2.pk]["module_detail"]["title"], "1-modul")
        self.assertFalse(rows[self.lab1.pk]["locked"])
        self.assertEqual(rows[self.lab1.pk]["description"], "Sodda sharti")

        response = self.client.get(f"/api/labs/{self.lab2.pk}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIs(response.data["locked"], True)
        self.assertEqual(response.data["blocked_by"]["id"], self.lab1.pk)
        # Kodni ishga tushirish, AI va tavsiya ham yopiq
        self.assertEqual(self.client.post(f"/api/labs/{self.lab2.pk}/run/", {"sql_code": "SELECT 1;"}, format="json").status_code, 403)
        self.assertEqual(self.client.get(f"/api/labs/{self.lab2.pk}/chat/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/labs/{self.lab2.pk}/study-advice/").status_code, 403)

        self.attempt(self.lab1, True)
        self.assertEqual(self.client.get(f"/api/labs/{self.lab2.pk}/").status_code, status.HTTP_200_OK)

    def test_staff_is_never_locked(self):
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get(f"/api/labs/{self.lab3.pk}/").status_code, status.HTTP_200_OK)

    def test_recommendation_follows_chain(self):
        self.client.force_authenticate(self.student)
        response = self.client.get("/api/labs/recommendations/")
        self.assertEqual(response.data["next"]["id"], self.lab1.pk)
        self.attempt(self.lab1, True)
        self.assertEqual(self.client.get("/api/labs/recommendations/").data["next"]["id"], self.lab2.pk)

    def test_module_management(self):
        self.client.force_authenticate(self.teacher)
        response = self.client.post("/api/lab-modules/", {"title": "Yangi", "order": 5}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        module_id = response.data["id"]
        self.assertTrue(response.data["sequential"])
        url = f"/api/lab-modules/{module_id}/reorder/"
        response = self.client.post(url, {"labs": [self.free.pk, self.lab3.pk]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data["labs"]], [self.free.pk, self.lab3.pk])
        self.lab3.refresh_from_db()
        self.assertEqual((self.lab3.module_id, self.lab3.position), (module_id, 2))
        # Ro'yxatdan chiqarilgani moduldan ham chiqadi
        self.client.post(url, {"labs": [self.lab3.pk]}, format="json")
        self.free.refresh_from_db()
        self.assertIsNone(self.free.module_id)
        for bad in ({"labs": "x"}, {"labs": [self.lab1.pk, self.lab1.pk]}, {"labs": [True]}):
            self.assertEqual(self.client.post(url, bad, format="json").status_code, status.HTTP_400_BAD_REQUEST)

        # Boshqa o'qituvchi: modulni ko'rmaydi, o'z laboratoriyasini begona modulga qo'sha olmaydi
        self.client.force_authenticate(self.other_teacher)
        self.assertEqual(self.client.get(f"/api/lab-modules/{module_id}/").status_code, status.HTTP_404_NOT_FOUND)
        own = Lab.objects.create(title="Begona", description="x", author=self.other_teacher)
        response = self.client.patch(f"/api/labs/{own.pk}/", {"module": module_id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("module", response.data)
        own_module = LabModule.objects.create(title="O'ziniki", author=self.other_teacher)
        self.assertEqual(
            self.client.post(f"/api/lab-modules/{own_module.pk}/reorder/", {"labs": [self.lab1.pk]}, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(self.client.patch(f"/api/labs/{own.pk}/", {"level": 6}, format="json").status_code, status.HTTP_400_BAD_REQUEST)

        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get("/api/lab-modules/").status_code, status.HTTP_403_FORBIDDEN)

    # ---------- Tavsiya ----------

    def advice_url(self, lab=None):
        return f"/api/labs/{(lab or self.lab1).pk}/study-advice/"

    def test_advice_needs_enough_wrong_attempts(self):
        self.client.force_authenticate(self.control_student)
        self.attempt(self.lab1, False, self.control_student)
        state = self.client.get(self.advice_url()).data
        self.assertEqual((state["wrong_attempts"], state["can_request"], state["advice"]), (1, False, None))
        self.assertEqual(self.client.post(self.advice_url()).status_code, status.HTTP_400_BAD_REQUEST)

    def test_control_group_gets_rule_based_advice(self):
        self.client.force_authenticate(self.control_student)
        for _ in range(MIN_WRONG):
            self.attempt(self.lab1, False, self.control_student)
        with patch("labs.study_advice.create_message") as create:
            response = self.client.post(self.advice_url())
        create.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        advice = response.data["advice"]
        self.assertEqual(advice["source"], "rules")
        self.assertIn("Ustun nomini tekshiring.", advice["struggles"][0]["explanation"])
        self.assertIn(f"{MIN_WRONG} ta urinishda", advice["struggles"][0]["explanation"])
        self.assertTrue(advice["steps"])
        self.assertTrue(response.data["fresh"])
        self.assertFalse(response.data["can_request"])
        # Yangi urinishsiz qayta so'ralsa — o'sha tavsiya, yangisi tuzilmaydi
        self.client.post(self.advice_url())
        self.assertEqual(StudyAdvice.objects.filter(student=self.control_student).count(), 1)

    @override_settings(GEMINI_API_KEY="test", AI_PROVIDER="gemini")
    def test_ai_advice_is_cached_until_new_attempt(self):
        self.client.force_authenticate(self.student)
        for _ in range(MIN_WRONG):
            self.attempt(self.lab1, False)
        content = {
            "summary": "Ustun nomlarini chalkashtiryapsiz.",
            "struggles": [{"title": "Ustun nomi", "explanation": "Jadvalda bunday ustun yo'q."}],
            "steps": ["SELECT * bilan jadvalni ko'ring.", "Ustun nomini tuzating."],
            "review": ["SELECT asoslari"],
        }
        with patch("labs.study_advice.create_message", return_value=fake_ai_response(content)) as create:
            response = self.client.post(self.advice_url())
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(response.data["advice"]["source"], "ai")
            self.assertEqual(response.data["advice"]["summary"], content["summary"])
            prompt = create.call_args.kwargs["messages"][0]["content"]
            self.assertIn("— 2 marta", prompt)
            self.assertNotIn("SELECT 1;", prompt)  # namunaviy yechim yuborilmaydi
            self.client.post(self.advice_url())
            self.assertEqual(create.call_count, 1)
            self.attempt(self.lab1, False)
            self.assertTrue(self.client.get(self.advice_url()).data["can_request"])
            self.client.post(self.advice_url())
            self.assertEqual(create.call_count, 2)
        self.assertEqual(AIAction.objects.filter(student=self.student, kind=AIAction.Kind.STUDY_ADVICE).count(), 2)

    @override_settings(GEMINI_API_KEY="test", AI_PROVIDER="gemini")
    def test_ai_failure_is_reported_and_not_counted(self):
        self.client.force_authenticate(self.student)
        for _ in range(MIN_WRONG):
            self.attempt(self.lab1, False)
        with patch("labs.study_advice.create_message", side_effect=AITransientError("band")):
            response = self.client.post(self.advice_url())
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertFalse(StudyAdvice.objects.exists())
        self.assertFalse(AIAction.objects.exists())

    def test_staff_cannot_request_advice(self):
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get(self.advice_url()).status_code, status.HTTP_403_FORBIDDEN)
