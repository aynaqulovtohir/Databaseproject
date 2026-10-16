"""Fon jarayoni: Telegram bot.

To'rt ish qiladi: /start va /stop buyruqlarini qabul qiladi, navbatdagi
bildirishnomalarni yuboradi, muddat eslatmalarini yaratadi va backend hamda
bazalar ishlamay qolsa, adminlarga xabar beradi (monitoring).

Ishga tushirish: python manage.py run_telegram_bot
"""
import logging
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from notifications import bot, monitor, services, telegram

NOT_CONFIGURED_SLEEP_SECONDS = 30
ERROR_SLEEP_SECONDS = 10
REMINDER_INTERVAL_SECONDS = 60

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Telegram bot: buyruqlarni qabul qiladi va bildirishnomalarni yuboradi"

    def handle(self, *args, **options):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        self.stdout.write("Telegram bot ishga tushdi")
        warned_not_configured = False
        offset = None
        last_reminder_check = 0.0
        health_monitor = monitor.Monitor()
        last_health_check = 0.0

        while True:
            if not telegram.is_configured():
                if not warned_not_configured:
                    self.stdout.write(
                        "TELEGRAM_BOT_TOKEN yoki TELEGRAM_BOT_USERNAME ko'rsatilmagan. Bot kutib turadi."
                    )
                    warned_not_configured = True
                time.sleep(NOT_CONFIGURED_SLEEP_SECONDS)
                continue

            # Alohida: baza ishlamay qolganda ham monitoring ishlashi kerak
            if monitor.is_enabled() and time.monotonic() - last_health_check >= monitor.CHECK_INTERVAL_SECONDS:
                last_health_check = time.monotonic()
                try:
                    health_monitor.check()
                except Exception:  # noqa: BLE001
                    logger.exception("Monitoring xatosi")

            try:
                for update in telegram.get_updates(offset=offset):
                    offset = update["update_id"] + 1
                    bot.handle_update(update)

                if time.monotonic() - last_reminder_check >= REMINDER_INTERVAL_SECONDS:
                    services.create_deadline_reminders()
                    # Haftalik erta ogohlantirish: har bir o'qituvchiga haftasiga ko'pi bilan bir marta
                    services.create_risk_digests()
                    last_reminder_check = time.monotonic()

                bot.send_pending()
            except telegram.TelegramError as exc:
                logger.warning("Telegram xatosi: %s", exc)
                time.sleep(ERROR_SLEEP_SECONDS)
            except Exception:  # masalan, baza vaqtincha uzilgan
                logger.exception("Bot xatosi")
                # Uzilgan ulanish yopiladi, baza tiklanganda keyingi so'rov yangisini ochadi
                close_old_connections()
                time.sleep(ERROR_SLEEP_SECONDS)
