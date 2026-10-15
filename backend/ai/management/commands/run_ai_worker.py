"""Fon jarayoni: navbatdagi AI tahlillarini birma-bir bajaradi.

Ishga tushirish: python manage.py run_ai_worker
"""
import logging
import time

from django.core.management.base import BaseCommand

from ai.client import is_configured
from ai.worker import process_next, release_stuck_analyses

IDLE_SLEEP_SECONDS = 3
NOT_CONFIGURED_SLEEP_SECONDS = 30
ERROR_SLEEP_SECONDS = 10


class Command(BaseCommand):
    help = "Navbatdagi AI tahlillarini bajaradi"

    def handle(self, *args, **options):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        self.stdout.write("AI worker ishga tushdi")
        warned_not_configured = False

        while True:
            if not is_configured():
                if not warned_not_configured:
                    self.stdout.write(
                        "AI kaliti (.env) ko'rsatilmagan. Tahlillar navbatda kutib turadi."
                    )
                    warned_not_configured = True
                time.sleep(NOT_CONFIGURED_SLEEP_SECONDS)
                continue

            try:
                release_stuck_analyses()
                did_work = process_next()
            except Exception:  # masalan, baza vaqtincha uzilgan
                logging.getLogger(__name__).exception("Worker xatosi")
                time.sleep(ERROR_SLEEP_SECONDS)
                continue

            if not did_work:
                time.sleep(IDLE_SLEEP_SECONDS)
