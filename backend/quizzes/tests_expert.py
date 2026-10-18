"""Ekspert baholashi: havolalar (token xavfsizligi), baholarni tekshirish, CVR / CVI / kappa va ruxsatlar."""
import hashlib

from django.core.cache import cache
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import User

from .expert import cvr_critical, i_cvi_target, kappa_label
from .models import Choice, ExpertInvite, ExpertPanel, Question, Quiz


class FormulaTests(SimpleTestCase):
    def test_cvr_critical_matches_ayre_scally(self):
        # Ayre & Scally (2014), 1-jadval: N = 5 → 1.00, 8 → 0.75, 10 → 0.80, 20 → 0.50
        self.assertEqual([cvr_critical(n) for n in (5, 8, 10, 20)], [1.0, 0.75, 0.8, 0.5])
        self.assertEqual(cvr_critical(6), 1.0)
        self.assertIsNone(cvr_critical(4))  # hatto hamma "zarur" desa ham tasodifdan farq qilmaydi
        self.assertIsNone(cvr_critical(0))

    def test_targets_and_labels(self):
        self.assertEqual((i_cvi_target(5), i_cvi_target(6)), (1.0, 0.78))
        self.assertEqual([kappa_label(value) for value in (0.8, 0.6, 0.45, 0.2)], ["a'lo", "yaxshi", "qoniqarli", "past"])


class ExpertPanelTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user("x_teacher", role=User.Role.TEACHER)
        cls.other = User.objects.create_user("x_other", role=User.Role.TEACHER)
        cls.student = User.objects.create_user("x_student", role=User.Role.STUDENT)
        cls.quiz = Quiz.objects.create(kind=Quiz.Kind.PRE, title="Kirish testi", author=cls.teacher)
        for order in range(1, 4):
            question = Question.objects.create(quiz=cls.quiz, order=order, text=f"Savol {order}", points=1)
            Choice.objects.create(question=question, order=1, text="To'g'ri", is_correct=True)
            Choice.objects.create(question=question, order=2, text="Xato", is_correct=False)
        cls.other_quiz = Quiz.objects.create(kind=Quiz.Kind.PRE, title="Begona", author=cls.other)
        Question.objects.create(quiz=cls.other_quiz, order=1, text="x", points=1)

    def setUp(self):
        cache.clear()

    def create_panel(self):
        self.client.force_authenticate(self.teacher)
        response = self.client.post(
            "/api/expert-panels/",
            {"quiz": self.quiz.pk, "title": "1-bosqich", "construct": "MB loyihalash bo'yicha bilim"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data

    def invite(self, panel_id, label="Ekspert"):
        self.client.force_authenticate(self.teacher)
        response = self.client.post(f"/api/expert-panels/{panel_id}/invites/", {"label": label}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def rate(self, token, ratings, submit=True, name="Prof. Ekspert"):
        self.client.force_authenticate(None)
        return self.client.put(
            f"/api/expert/{token}/", {"expert": {"full_name": name, "degree": "PhD"}, "ratings": ratings, "submit": submit}, format="json"
        )

    @staticmethod
    def full(essential, relevance, clarity=4):
        return {"essential": essential, "relevance": relevance, "clarity": clarity}

    def test_snapshot_and_token_is_stored_hashed(self):
        panel = self.create_panel()
        self.assertEqual(panel["items_count"], 3)
        self.assertEqual(panel["quiz_title"], "Kirish testi")
        data = self.invite(panel["id"], "1-ekspert, TATU")
        token = data["token"]
        invite = ExpertInvite.objects.get(pk=data["invite"]["id"])
        self.assertEqual(invite.token_hash, hashlib.sha256(token.encode()).hexdigest())
        self.assertNotIn(token, str(ExpertInvite.objects.values().get(pk=invite.pk)))
        # Ro'yxatda token qaytmaydi
        self.assertNotIn("token", self.client.get(f"/api/expert-panels/{panel['id']}/").data["invites"][0])
        # Test tahrirlansa ham ekspert eski versiyani baholaydi
        Question.objects.filter(quiz=self.quiz, order=1).update(text="O'zgargan")
        self.client.force_authenticate(None)
        page = self.client.get(f"/api/expert/{token}/").data
        self.assertEqual(page["items"][0]["text"], "Savol 1")
        self.assertTrue(page["items"][0]["choices"][0]["is_correct"])

    def test_rating_flow(self):
        panel = self.create_panel()
        token = self.invite(panel["id"])["token"]
        # Oraliq saqlash: to'liq bo'lmasa ham mumkin
        response = self.rate(token, {"1": {"essential": 3}}, submit=False)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["ratings"]["1"], {"essential": 3, "comment": ""})
        # Yuborishda hamma savol baholangan bo'lishi kerak
        response = self.rate(token, {"1": self.full(3, 4)}, submit=True)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Baholanmagan: 2, 3", response.data["detail"])
        complete = {key: self.full(3, 4) for key in ("1", "2", "3")}
        self.assertEqual(self.rate(token, complete, name="").status_code, status.HTTP_400_BAD_REQUEST)
        response = self.rate(token, complete)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["submitted_at"])
        # Yuborilgandan keyin o'zgartirib bo'lmaydi
        self.assertEqual(self.rate(token, complete).status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_ratings(self):
        panel = self.create_panel()
        token = self.invite(panel["id"])["token"]
        for bad in ({"9": {"essential": 3}}, {"1": {"essential": 4}}, {"1": {"relevance": 0}}, {"1": {"clarity": True}},
                    {"1": {"comment": "x" * 1001}}, {"1": "3"}, []):
            self.assertEqual(self.rate(token, bad, submit=False).status_code, status.HTTP_400_BAD_REQUEST, bad)
        self.assertEqual(self.client.get("/api/expert/notatoken/").status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get("/api/expert/" + "a" * 43 + "/").status_code, status.HTTP_404_NOT_FOUND)

    def test_revoke_renew_and_closing(self):
        panel = self.create_panel()
        data = self.invite(panel["id"])
        token, invite_id = data["token"], data["invite"]["id"]
        self.client.force_authenticate(self.teacher)
        base = f"/api/expert-panels/{panel['id']}/invites/{invite_id}"
        self.client.post(f"{base}/revoke/")
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(f"/api/expert/{token}/").status_code, status.HTTP_404_NOT_FOUND)
        self.client.force_authenticate(self.teacher)
        new_token = self.client.post(f"{base}/renew/").data["token"]
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(f"/api/expert/{token}/").status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(f"/api/expert/{new_token}/").status_code, status.HTTP_200_OK)
        ExpertPanel.objects.filter(pk=panel["id"]).update(closes_at=timezone.now())
        self.assertEqual(self.rate(new_token, {}, submit=False).status_code, status.HTTP_400_BAD_REQUEST)

    def test_permissions(self):
        panel = self.create_panel()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/expert-panels/{panel['id']}/").status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(f"/api/expert-panels/{panel['id']}/invites/", {"label": "x"}, format="json").status_code, 404)
        self.client.force_authenticate(self.teacher)
        response = self.client.post("/api/expert-panels/", {"quiz": self.other_quiz.pk, "title": "x", "construct": "x"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("quiz", response.data)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get("/api/expert-panels/").status_code, status.HTTP_403_FORBIDDEN)

    def test_results(self):
        panel = self.create_panel()
        # 6 ekspert. 1-savol: hamma zarur va mos; 2-savol: 4 zarur, 5 mos; 3-savol: 1 zarur, 2 mos
        plans = [
            ({"1": (3, 4), "2": (3, 4), "3": (3, 4)}),
            ({"1": (3, 4), "2": (3, 3), "3": (2, 3)}),
            ({"1": (3, 3), "2": (3, 4), "3": (2, 2)}),
            ({"1": (3, 4), "2": (3, 3), "3": (1, 1)}),
            ({"1": (3, 4), "2": (2, 3), "3": (2, 2)}),
            ({"1": (3, 4), "2": (2, 2), "3": (1, 2)}),
        ]
        for number, plan in enumerate(plans, start=1):
            token = self.invite(panel["id"], f"{number}-ekspert")["token"]
            ratings = {key: self.full(*values) for key, values in plan.items()}
            ratings["3"]["comment"] = "Variantlar noaniq" if number == 1 else ""
            self.assertEqual(self.rate(token, ratings, name=f"Ekspert {number}").status_code, status.HTTP_200_OK)
        self.invite(panel["id"], "yubormagan")  # hisobga kirmaydi
        self.client.force_authenticate(self.teacher)
        result = self.client.get(f"/api/expert-panels/{panel['id']}/").data["results"]
        self.assertEqual((result["experts"], result["invited"]), (6, 7))
        self.assertEqual(result["cvr_critical"], 1.0)  # N = 6: hamma ekspert "zarur" deyishi kerak
        items = {item["key"]: item for item in result["items"]}
        self.assertEqual((items["1"]["cvr"], items["1"]["i_cvi"], items["1"]["verdict"]["key"]), (1.0, 1.0, "keep"))
        self.assertEqual((items["2"]["essential"], items["2"]["cvr"]), (4, 0.33))
        self.assertEqual(items["2"]["i_cvi"], 0.83)
        self.assertEqual(items["2"]["kappa"], 0.82)  # (5/6 − 6/64) / (1 − 6/64)
        self.assertEqual(items["2"]["verdict"]["key"], "revise")  # CVR kritikdan past
        self.assertEqual((items["3"]["cvr"], items["3"]["i_cvi"], items["3"]["verdict"]["key"]), (-0.67, 0.33, "remove"))
        self.assertEqual(items["3"]["comments"], ["Variantlar noaniq"])
        summary = result["summary"]
        self.assertEqual(summary["s_cvi_ave"], round((1 + 5 / 6 + 2 / 6) / 3, 2))
        self.assertEqual(summary["s_cvi_ua"], 0.33)
        self.assertFalse(summary["s_cvi_ave_ok"])
        self.assertEqual((summary["keep"], summary["revise"], summary["remove"]), (1, 1, 1))
        self.assertEqual([expert["full_name"] for expert in result["panel_experts"]][:2], ["Ekspert 1", "Ekspert 2"])
