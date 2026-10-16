"""O'zaro baholash: navbat, anonimlik, rubrika, "foydali" belgisi va kompetentlik ko'rsatkichlari."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework import status

from competence.models import Component, Indicator
from users.models import User

from .design_labs import ER_LABS
from .models import Lab, LabAttempt, PeerReview
from .peer_review import accuracy, structural_score
from .tests import PASSWORD, BaseTestCase

REFERENCE = ER_LABS[0]["reference_diagram"]
PARTIAL = {"entities": [REFERENCE["entities"][0]], "relationships": []}
GOOD = {"entities": 4, "attributes": 4, "relationships": 4, "clarity": 4}
COMMENT = "Obyektlar to'g'ri, lekin talaba va fan orasidagi bog'lanish yetishmaydi."


class PeerMathTests(SimpleTestCase):
    def test_accuracy(self):
        self.assertEqual(structural_score({"entities": 1, "attributes": 1, "relationships": 1}), 0)
        self.assertEqual(accuracy(SimpleNamespace(scores=GOOD, reference_ratio=1.0)), 100)
        self.assertEqual(accuracy(SimpleNamespace(scores={**GOOD, "entities": 1, "attributes": 1, "relationships": 1}, reference_ratio=1.0)), 0)
        self.assertEqual(accuracy(SimpleNamespace(scores=GOOD, reference_ratio=0.25)), 25)


class PeerReviewApiTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        data = {key: value for key, value in ER_LABS[0].items() if key != "theory"}
        cls.er_lab = Lab.objects.create(**data, author=cls.teacher_a)
        cls.er_lab.groups.add(cls.group_a, cls.group_b)
        cls.url = f"/api/labs/{cls.er_lab.pk}/peer-review/"
        cls.student_a3 = User.objects.create_user("student_a3", password=PASSWORD, role=User.Role.STUDENT, group=cls.group_a)

    def submit(self, student, diagram, correct):
        return LabAttempt.objects.create(lab=self.er_lab, student=student, diagram=diagram, is_correct=correct, is_submission=True)

    def review(self, attempt_id, scores=GOOD, comment=COMMENT):
        return self.client.post(self.url, {"attempt": attempt_id, "scores": scores, "comment": comment}, format="json")

    def test_must_solve_first(self):
        self.submit(self.student_a2, PARTIAL, False)
        self.auth_as(self.student_a1)
        data = self.client.get(self.url).data
        self.assertIsNone(data["current"])
        self.assertIn("o'zingiz to'g'ri yeching", data["reason"])
        attempt = LabAttempt.objects.get(student=self.student_a2)
        self.assertEqual(self.review(attempt.pk).status_code, status.HTTP_400_BAD_REQUEST)

    def test_queue_is_anonymous_and_limited_to_own_group(self):
        own = self.submit(self.student_a1, REFERENCE, True)
        peer = self.submit(self.student_a2, PARTIAL, False)
        self.submit(self.student_b, PARTIAL, False)  # boshqa guruh — berilmaydi
        self.auth_as(self.student_a1)
        data = self.client.get(self.url).data
        self.assertEqual(data["current"]["attempt_id"], peer.pk)
        self.assertNotIn("student_a2", str(data))
        self.assertNotIn("student", data["current"])
        # Baholagandan keyin o'z ishi ham, boshqa guruh ishi ham navbatga chiqmaydi
        response = self.review(peer.pk)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIsNone(response.data["current"])
        self.assertEqual(response.data["written"], 1)
        saved = PeerReview.objects.get()
        self.assertEqual((saved.attempt, saved.reviewer), (peer, self.student_a1))
        self.assertLess(saved.reference_ratio, 1.0)
        self.assertNotEqual(own.pk, data["current"]["attempt_id"])

    def test_only_the_offered_attempt_can_be_reviewed(self):
        self.submit(self.student_a1, REFERENCE, True)
        first = self.submit(self.student_a2, PARTIAL, False)
        second = self.submit(self.student_a3, REFERENCE, True)
        self.auth_as(self.student_a1)
        offered = self.client.get(self.url).data["current"]["attempt_id"]
        other = second.pk if offered == first.pk else first.pk
        self.assertEqual(self.review(other).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.review(offered).status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.client.get(self.url).data["current"]["attempt_id"], other)

    def test_least_reviewed_attempt_comes_first(self):
        first = self.submit(self.student_a2, PARTIAL, False)
        second = self.submit(self.student_a3, PARTIAL, False)
        self.submit(self.student_a1, REFERENCE, True)
        PeerReview.objects.create(attempt=first, reviewer=self.student_a3, scores=GOOD, comment=COMMENT, reference_ratio=0.5)
        self.auth_as(self.student_a1)
        self.assertEqual(self.client.get(self.url).data["current"]["attempt_id"], second.pk)

    def test_validation(self):
        self.submit(self.student_a1, REFERENCE, True)
        peer = self.submit(self.student_a2, PARTIAL, False)
        self.auth_as(self.student_a1)
        for scores, comment in (
            ({**GOOD, "clarity": 5}, COMMENT),
            ({"entities": 4}, COMMENT),
            ({**GOOD, "entities": True}, COMMENT),
            (GOOD, "Yaxshi"),
        ):
            self.assertEqual(self.review(peer.pk, scores, comment).status_code, status.HTTP_400_BAD_REQUEST, (scores, comment))
        self.assertFalse(PeerReview.objects.exists())

    def test_reviews_per_lab_limit(self):
        self.submit(self.student_a1, REFERENCE, True)
        self.submit(self.student_a2, PARTIAL, False)
        self.submit(self.student_a3, PARTIAL, False)
        self.auth_as(self.student_a1)
        with patch("labs.peer_review.REVIEWS_PER_LAB", 1):
            self.assertEqual(self.review(self.client.get(self.url).data["current"]["attempt_id"]).status_code, 201)
            data = self.client.get(self.url).data
            self.assertIsNone(data["current"])
            self.assertIn("Rahmat", data["reason"])

    def test_author_sees_review_and_marks_helpful(self):
        self.submit(self.student_a1, REFERENCE, True)
        peer = self.submit(self.student_a2, PARTIAL, False)
        self.auth_as(self.student_a1)
        self.review(peer.pk)
        review = PeerReview.objects.get()
        helpful_url = f"/api/labs/peer-reviews/{review.pk}/helpful/"
        # Baholovchi ham, boshqa talaba ham belgilay olmaydi
        self.assertEqual(self.client.post(helpful_url, {"helpful": True}, format="json").status_code, 404)
        self.auth_as(self.student_a3)
        self.assertEqual(self.client.post(helpful_url, {"helpful": True}, format="json").status_code, 404)
        self.auth_as(self.student_a2)
        received = self.client.get(self.url).data["received"]
        self.assertEqual([(item["id"], item["comment"]) for item in received], [(review.pk, COMMENT)])
        self.assertNotIn("student_a1", str(received))
        self.assertEqual(self.client.post(helpful_url, {"helpful": "ha"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(helpful_url, {"helpful": True}, format="json").data["helpful"], True)
        review.refresh_from_db()
        self.assertTrue(review.helpful)

    def test_access(self):
        self.auth_as(self.teacher_a)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)
        self.auth_as(self.student_a1)
        self.assertEqual(self.client.get(f"/api/labs/{self.lab.pk}/peer-review/").status_code, status.HTTP_403_FORBIDDEN)

    def test_competence_indicators(self):
        accuracy_component = Component.objects.create(name="Refleksiv", order=1)
        helpful_component = Component.objects.create(name="Kommunikativ", order=2)
        Indicator.objects.create(component=accuracy_component, name="Aniqlik", source=Indicator.Source.PEER_ACCURACY)
        Indicator.objects.create(component=helpful_component, name="Foydalilik", source=Indicator.Source.PEER_HELPFUL)
        first = self.submit(self.student_a2, PARTIAL, False)
        second = self.submit(self.student_a3, REFERENCE, True)
        # Ikkala ish ham to'liq (4) baholangan: to'g'ri ish (moslik 1.0) → aniqlik 100, qisman ish (0.5) → 50
        PeerReview.objects.create(attempt=second, reviewer=self.student_a1, scores=GOOD, comment=COMMENT, reference_ratio=1.0, helpful=True)
        PeerReview.objects.create(attempt=first, reviewer=self.student_a1, scores=GOOD, comment=COMMENT, reference_ratio=0.5, helpful=False)
        self.auth_as(self.teacher_a)
        rows = {row["id"]: row for row in self.client.get("/api/competence/report/", {"group": self.group_a.pk, "stage": "final"}).data["students"]}
        scores = rows[self.student_a1.pk]["components"]
        self.assertEqual(scores[str(accuracy_component.pk)]["score"], 75.0)  # (100 + 50) / 2
        self.assertEqual(scores[str(helpful_component.pk)]["score"], 50.0)  # 1 / 2 foydali
        self.assertIsNone(rows[self.student_a2.pk]["components"][str(accuracy_component.pk)]["score"])  # baholamagan
