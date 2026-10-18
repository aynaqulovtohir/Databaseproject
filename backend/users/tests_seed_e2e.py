import os
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class SeedE2EGuardTests(SimpleTestCase):
    """seed_e2e parollari ma'lum hisoblar yaratadi: faqat E2E=1 va *_e2e bazada ishlashi kerak."""

    def assert_refused(self, e2e_flag, db_name):
        environ = {k: v for k, v in os.environ.items() if k != "E2E"}
        if e2e_flag is not None:
            environ["E2E"] = e2e_flag
        with (
            patch.dict(os.environ, environ, clear=True),
            patch.dict(settings.DATABASES["default"], {"NAME": db_name}),
            patch("users.management.commands.seed_e2e.Command.recreate_database") as recreate,
        ):
            with self.assertRaises(CommandError):
                call_command("seed_e2e")
            recreate.assert_not_called()

    def test_e2e_belgisisiz_ishlamaydi(self):
        self.assert_refused(None, "dbproject_e2e")

    def test_oddiy_bazada_ishlamaydi(self):
        self.assert_refused("1", "dbproject")

    def test_belgi_faqat_1_bolsa(self):
        self.assert_refused("true", "dbproject_e2e")
