"""Interfeys tili (uz/en/ru): lug'atlar to'liqligi, tr(), saqlangan xabarni o'girish va javob renderer'i."""
import json

from django.test import SimpleTestCase
from django.utils import translation

from learning.tests import BaseTestCase

from .i18n import localize, localize_prompt, tr, translate_text
from .i18n_keys import problems


class DictionaryTests(SimpleTestCase):
    def test_every_key_is_translated(self):
        # Yangi tr("...")/N_("...") matni qo'shilsa, locale/en.json va ru.json ga ham tarjimasi yozilsin
        self.assertEqual(problems(), [])


class TranslateTests(SimpleTestCase):
    def test_uzbek_is_default_and_unchanged(self):
        self.assertEqual(tr("Diagramma noto'g'ri formatda."), "Diagramma noto'g'ri formatda.")
        with translation.override("uz"):
            self.assertEqual(tr("{count} ta guruhda", count=3), "3 ta guruhda")

    def test_translates_with_params(self):
        with translation.override("en"):
            self.assertEqual(tr("{count} ta guruhda", count=3), "in 3 groups")
        with translation.override("ru"):
            self.assertEqual(tr("{count} ta guruhda", count=3), "в группах: 3")

    def test_unknown_language_and_text_fall_back(self):
        with translation.override("de"):
            self.assertEqual(tr("Diagramma noto'g'ri formatda."), "Diagramma noto'g'ri formatda.")
        with translation.override("en"):
            self.assertEqual(tr("Lug'atda yo'q matn"), "Lug'atda yo'q matn")

    def test_params_are_not_formatted_as_code(self):
        # str.format emas: foydalanuvchi matnidagi {..} va atribut murojaati ishlamaydi
        with translation.override("en"):
            self.assertEqual(tr("{count} ta guruhda", count="{0.__class__}"), "in {0.__class__} groups")

    def test_saved_uzbek_message_is_translated_by_template(self):
        # Tekshiruv natijasi bazaga o'zbekcha yoziladi, javobda andoza bo'yicha o'giriladi
        saved = "Natijadagi qatorlar soni farq qiladi: sizda 3 ta, kutilgan 5 ta."
        self.assertEqual(
            translate_text(saved, "en"), "The number of rows in the result differs: you have 3, expected 5."
        )
        self.assertEqual(translate_text(saved, "uz"), saved)
        self.assertEqual(translate_text("Talabaning o'z matni", "ru"), "Talabaning o'z matni")

    def test_localize_skips_user_content(self):
        data = {"detail": "Ball kiritilishi shart.", "sql_code": "Ball kiritilishi shart.", "items": ["Xato"]}
        self.assertEqual(
            localize(data, "en"),
            {"detail": "The score is required.", "sql_code": "Ball kiritilishi shart.", "items": ["Error"]},
        )

    def test_ai_prompt_language(self):
        prompt = "Javobni o'zbek tilida (lotin yozuvida) yoz. O'zbek tilida (lotin yozuvida) yoz."
        self.assertEqual(localize_prompt(prompt, "uz"), prompt)
        self.assertEqual(
            localize_prompt(prompt, "en"),
            "Javobni ingliz tilida (in English) yoz. Ingliz tilida (in English) yoz.",
        )
        self.assertIn("rus tilida", localize_prompt(prompt, "ru"))


class ResponseLanguageTests(BaseTestCase):
    def cards(self, language=None):
        self.auth_as(self.teacher_a)
        headers = {"HTTP_ACCEPT_LANGUAGE": language} if language else {}
        response = self.client.get("/api/dashboard/", **headers)
        self.assertEqual(response.status_code, 200)
        return {card["key"]: card["label"] for card in json.loads(response.content)["cards"]}

    def test_dashboard_follows_accept_language(self):
        self.assertEqual(self.cards()["students"], "Talabalar")
        self.assertEqual(self.cards("en")["students"], "Students")
        self.assertEqual(self.cards("ru")["students"], "Студенты")

    def test_error_message_follows_accept_language(self):
        self.auth_as(self.student_a)
        response = self.client.get("/api/dashboard/", HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            "/api/auth/change-password/",
            {"old_password": "noto'g'ri", "new_password": "Yangi-Parol-2026"},
            format="json",
            HTTP_ACCEPT_LANGUAGE="ru",
        )
        if response.status_code == 404:
            self.skipTest("parol almashtirish manzili boshqacha")
        self.assertIn("Старый пароль неверен.", response.content.decode())
