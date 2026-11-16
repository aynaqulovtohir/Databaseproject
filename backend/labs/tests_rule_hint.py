"""Nazorat guruhi uchun xato turi bo'yicha tayyor tushuntirish (AI'siz, talaba so'raganda)."""
from datetime import timedelta

from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework import status

from .models import Lab, LabAttempt, LabModule
from .rule_hints import GENERAL, MAX_HINTS, explanation_for, rule_hints
from .tests import ER_REFERENCE, ER_WRONG, SOLUTION, BaseTestCase


class RuleTextTests(SimpleTestCase):
    def test_each_checker_message_has_an_explanation(self):
        samples = [
            "2 ta obyekt yetishmaydi.",  # er.py
            "«Talaba» — «Guruh» bog'lanishining kardinalligi noto'g'ri (sizda 1:1). Bitta …",
            "«Talaba» obyektida asosiy kalit (PK) belgilanmagan.",
            "«Talaba» va «Guruh» orasida bog'lanish yetishmaydi.",
            "Hozirgi normal forma noto'g'ri: siz ko'rsatgan 3NF haqiqiysidan yuqori. …",  # norm.py
            "R2{shahar, narx} 3NF da emas: {shahar} -> {narx} bog'liqligida chap tomon bu jadvalda kalit emas.",
            "Dekompozitsiya yo'qotishli: jadvallarni qayta birlashtirganda …",
            "«kitob.isbn» ustuni NOT NULL bo'lishi kerak.",  # checker.py
            "«kitob» jadvalida UNIQUE cheklovi yetishmaydi yoki kutilganidan boshqacha.",
            "«Hamma nusxalar berildi (0 ta)» — rad etildi, lekin u to'g'ri ma'lumot.",  # probes.py
            "«Nomsiz kitob» — o'tib ketdi.",
        ]
        for text in samples:
            with self.subTest(text=text):
                self.assertIsNotNone(explanation_for(text))

    def test_explanation_does_not_reveal_the_answer(self):
        # Tushuntirish tushunchani nomlaydi, lekin kardinallik qiymatini aytmaydi
        text = explanation_for("«Talaba» — «Guruh» bog'lanishining kardinalligi noto'g'ri (sizda 1:1).")
        self.assertNotIn("Talaba", text)
        self.assertNotIn("Guruh", text)

    def test_sql_error_uses_tip_duplicates_merged_and_limited(self):
        error = LabAttempt(feedback={"error": {"sqlstate": "42601", "message": "syntax error", "tip": "Sintaksis tip"}})
        self.assertEqual(rule_hints(error), [{"problem": "syntax error", "explanation": "Sintaksis tip"}])
        many = LabAttempt(feedback={"differences": [f"{i} ta obyekt yetishmaydi." for i in range(1, 4)] + [
            "«A» obyektida asosiy kalit (PK) belgilanmagan.", "«A» obyektida 1 ta atribut yetishmaydi.",
            "«A» obyektida ortiqcha atribut: x.", "Ortiqcha obyekt: «B».", "«A» va «B» orasida ortiqcha bog'lanish bor.",
        ]})
        hints = rule_hints(many)
        self.assertEqual(len(hints), MAX_HINTS)
        self.assertEqual(len({hint["explanation"] for hint in hints}), MAX_HINTS)
        self.assertEqual(rule_hints(LabAttempt(feedback={"differences": ["Noma'lum farq."]}))[0]["explanation"], GENERAL)


@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="sinov-kaliti")
class RuleHintApiTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.group_a.ai_enabled = False  # nazorat guruhi
        cls.group_a.save()
        cls.lab.groups.add(cls.group_b)  # tajriba guruhi
        cls.er_lab = Lab.objects.create(
            kind=Lab.Kind.ER, title="ER", description="d", reference_diagram=ER_REFERENCE, author=cls.teacher_a
        )
        cls.er_lab.groups.add(cls.group_a)

    def hint_url(self, attempt_id):
        return f"/api/labs/attempts/{attempt_id}/rule-hint/"

    def test_control_group_gets_rule_hint_on_request_and_it_is_recorded(self):
        self.auth_as(self.student_a1)
        response = self.run_code("SELECT nomi FORM kitob;")
        self.assertFalse(response.data["ai_available"])
        self.assertTrue(response.data["rule_hint_available"])
        attempt = LabAttempt.objects.get(pk=response.data["attempt_id"])
        self.assertIsNone(attempt.rule_hint_at)  # avtomatik berilmaydi
        hint = self.client.post(self.hint_url(attempt.pk))
        self.assertEqual(hint.status_code, status.HTTP_200_OK)
        self.assertIn("Sintaksis", hint.data["hints"][0]["explanation"])
        attempt.refresh_from_db()
        self.assertIsNotNone(attempt.rule_hint_at)

    def test_er_attempt_gets_concept_explanations(self):
        self.auth_as(self.student_a1)
        response = self.client.post(f"/api/labs/{self.er_lab.pk}/submit/", {"diagram": ER_WRONG}, format="json")
        self.assertTrue(response.data["rule_hint_available"])
        hints = self.client.post(self.hint_url(response.data["attempt_id"])).data["hints"]
        self.assertTrue(hints)
        self.assertNotIn(GENERAL, [hint["explanation"] for hint in hints])

    def test_experimental_group_and_others_are_refused(self):
        self.auth_as(self.student_b)  # AI yoqilgan guruh
        response = self.run_code("SELECT nomi FORM kitob;")
        self.assertTrue(response.data["ai_available"])
        self.assertFalse(response.data["rule_hint_available"])
        self.assertEqual(self.client.post(self.hint_url(response.data["attempt_id"])).status_code, 403)
        # Boshqa talabaning urinishi — 404; to'g'ri urinish — 400
        self.auth_as(self.student_a2)
        self.assertEqual(self.client.post(self.hint_url(response.data["attempt_id"])).status_code, 404)
        self.auth_as(self.student_a1)
        correct = self.run_code(SOLUTION)
        self.assertFalse(correct.data["rule_hint_available"])
        self.assertEqual(self.client.post(self.hint_url(correct.data["attempt_id"])).status_code, 400)

    def test_off_during_exam(self):
        module = LabModule.objects.create(title="Imtihon", sequential=False, author=self.teacher_a)
        now = timezone.now()
        module.exam_starts_at, module.exam_ends_at = now - timedelta(minutes=5), now + timedelta(minutes=55)
        module.save()
        self.lab.module = module
        self.lab.save()
        self.auth_as(self.student_a1)
        response = self.run_code("SELECT nomi FORM kitob;")
        self.assertFalse(response.data["rule_hint_available"])
        self.assertEqual(self.client.post(self.hint_url(response.data["attempt_id"])).status_code, 403)
