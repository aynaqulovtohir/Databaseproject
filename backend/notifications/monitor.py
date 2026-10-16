"""Monitoring: backend va bazalar ishlayaptimi, nosozlik bo'lsa adminlarga Telegram xabari.

Bot ichki tarmoq orqali MONITOR_HEALTH_URL ni chaqiradi. Xabar faqat qaysi qism ishlamayotganini
aytadi: xato matni, manzil va boshqa ichki ma'lumotlar Telegram'ga yuborilmaydi.

Baza ishlamay qolganda ham adminlarga yozish uchun ularning chat raqamlari xotirada saqlab turiladi.
"""
import logging

import requests
from django.conf import settings
from django.db import connection

from users.models import User

from . import telegram
from .models import TelegramAccount

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 10
# Bir martalik qisqa uzilish (masalan, qayta ishga tushirish) uchun bezovta qilinmaydi
FAILURES_BEFORE_ALERT = 2

COMPONENTS = {
    "backend": "Backend (sayt serveri)",
    "database": "Asosiy baza",
    "lab_database": "Laboratoriya bazasi",
}


def is_enabled():
    return bool(settings.MONITOR_HEALTH_URL) and telegram.is_configured()


def _host_header():
    """Backend ALLOWED_HOSTS dagi nomni kutadi, ichki manzil (backend:8000) esa unda bo'lmasligi mumkin."""
    for host in settings.ALLOWED_HOSTS:
        host = host.strip().lstrip(".")
        if host and host != "*":
            return {"Host": host}
    return {}


def fetch_status():
    """Qaytaradi: {qism: True/False}. Backend javob bermasa, bazalar holati noma'lum (kalit yo'q)."""
    try:
        response = requests.get(
            settings.MONITOR_HEALTH_URL,
            headers=_host_header(),
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
        data = response.json()
    except (requests.RequestException, ValueError):
        return {"backend": False}
    if response.status_code not in (200, 503) or not isinstance(data, dict):
        return {"backend": False}
    return {"backend": True, "database": data.get("database") is True, "lab_database": data.get("lab_database") is True}


class Monitor:
    def __init__(self):
        self.failures = dict.fromkeys(COMPONENTS, 0)
        self.alerted = set()
        self.admin_chats = []

    def refresh_admin_chats(self):
        """Faol adminlarning chat raqamlari. Baza ishlamasa, oxirgi ma'lum ro'yxat qoladi."""
        try:
            self.admin_chats = list(
                TelegramAccount.objects.filter(user__role=User.Role.ADMIN, user__is_active=True)
                .order_by("chat_id")
                .values_list("chat_id", flat=True)
            )
        except Exception:  # noqa: BLE001 — asosiy baza ishlamayotgan bo'lishi mumkin
            logger.warning("Monitoring: adminlar ro'yxati yangilanmadi, oxirgisi ishlatiladi")
            # Uzilgan ulanish yopiladi, baza tiklanganda keyingi so'rov yangisini ochadi
            if connection.connection is not None and not connection.is_usable():
                connection.close()
        return self.admin_chats

    def check(self):
        """Bitta tekshiruv. Qaytaradi: yuborilgan xabar matni yoki None."""
        status = fetch_status()
        down, recovered = [], []
        for component, ok in status.items():
            if ok:
                self.failures[component] = 0
                if component in self.alerted:
                    recovered.append(component)
            else:
                self.failures[component] += 1
                if self.failures[component] >= FAILURES_BEFORE_ALERT and component not in self.alerted:
                    down.append(component)

        if not down and not recovered:
            return None
        lines = []
        if down:
            lines.append("⚠️ Nosozlik — javob bermayapti:")
            lines += [f"• {COMPONENTS[component]}" for component in down]
        if recovered:
            lines.append("✅ Qayta ishlayapti:")
            lines += [f"• {COMPONENTS[component]}" for component in recovered]
        text = "\n".join(lines)

        chats = self.refresh_admin_chats()
        if chats and not self._send(chats, text):
            # Hech kimga yetib bormadi (Telegram ishlamayapti): keyingi tekshiruvda qayta urinamiz
            return None
        self.alerted.update(down)
        self.alerted.difference_update(recovered)
        return text

    def _send(self, chats, text):
        delivered = False
        for chat_id in chats:
            try:
                telegram.send_message(chat_id, text)
                delivered = True
            except telegram.TelegramError as exc:
                logger.warning("Monitoring xabari yuborilmadi: %s", exc)
        return delivered
