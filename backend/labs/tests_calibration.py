"""O'z bilimini baholash aniqligi: ishonchni saqlash va kalibrlash hisobi."""
from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework import status

from competence.models import Component, Indicator

from .calibration import MIN_LABS, calibration, judgments
from .models import Lab, LabAttempt
from .tests import SOLUTION, BaseTestCase


def attempt(lab_id, confidence, correct):
    return SimpleNamespace(lab_id=lab_id, confidence=confidence, is_correct=correct)


class CalibrationMathTests(SimpleTestCase):
    def test_first_rated_attempt_per_lab(self):
        # 1-laboratoriya: ishonchsiz urinish hisobga olinmaydi, keyingi baholangani — birinchi mulohaza
        items = judgments([attempt(1, None, False), attempt(1, 5, False), attempt(1, 1, True), attempt(2, 3, True)])
        self.assertEqual(items, [(1.0, 0.0), (0.5, 1.0)])

    def test_score_and_bias(self):
        perfect = calibration([attempt(1, 5, True), attempt(2, 1, False), attempt(3, 5, True)])
        self.assertEqual((perfect["score"], perfect["bias"]), (100.0, 0.0))
        overconfident = calibration([attempt(1, 5, False), attempt(2, 5, False), attempt(3, 5, True)])
        self.assertAlmostEqual(overconfident["score"], 100 * (1 - 2 / 3))
        self.assertAlmostEqual(overconfident["bias"], 100 * 2 / 3)  # musbat — o'ziga ortiqcha ishongan

    def test_too_few_labs(self):
        self.assertIsNone(calibration([attempt(lab, 3, True) for lab in range(MIN_LABS - 1)]))


class ConfidenceApiTests(BaseTestCase):
    def run_with(self, confidence, url=None):
        return self.client.post(url or self.run_url, {"sql_code": SOLUTION, "confidence": confidence}, format="json")

    def test_confidence_is_stored_with_attempt(self):
        self.auth_as(self.student_a1)
        self.assertEqual(self.run_with(4).status_code, status.HTTP_200_OK)
        self.assertEqual(self.run_code(SOLUTION).status_code, status.HTTP_200_OK)  # ixtiyoriy
        self.assertEqual(list(LabAttempt.objects.order_by("id").values_list("confidence", flat=True)), [4, None])

    def test_invalid_confidence(self):
        self.auth_as(self.student_a1)
        for value in (0, 6, "4", True, 2.5):
            self.assertEqual(self.run_with(value).status_code, status.HTTP_400_BAD_REQUEST, value)
        self.assertFalse(LabAttempt.objects.exists())

    def test_competence_indicator(self):
        component = Component.objects.create(name="Refleksiv")
        Indicator.objects.create(component=component, name="Kalibrlash", source=Indicator.Source.CALIBRATION)
        labs = [self.lab]
        for number in range(2):
            lab = Lab.objects.create(title=f"Lab {number}", description="x", setup_sql="", author=self.teacher_a)
            lab.groups.add(self.group_a)
            labs.append(lab)
        # Ishonch 5 va to'g'ri, 5 va xato, 1 va xato → Brier = 1/3 → 66.7
        for lab, confidence, correct in zip(labs, (5, 5, 1), (True, False, False)):
            LabAttempt.objects.create(lab=lab, student=self.student_a1, sql_code="x", is_correct=correct, confidence=confidence)
        self.auth_as(self.teacher_a)
        rows = self.client.get("/api/competence/report/", {"group": self.group_a.pk, "stage": "final"}).data["students"]
        scores = {row["id"]: row["components"][str(component.pk)]["score"] for row in rows}
        self.assertEqual(scores[self.student_a1.pk], 66.7)
        self.assertIsNone(scores[self.student_a2.pk])  # ishonch belgilamagan — o'lchanmagan
