"""Holat tekshiruvi: asosiy va laboratoriya bazalari ishlayaptimi (monitoring uchun).

Faqat ha/yo'q qaytaradi (xato matni, manzil va versiyalar ko'rsatilmaydi). Natija qisqa muddat
keshlanadi: manzilni tez-tez chaqirib bazalarni band qilib bo'lmaydi. Kesh jarayon xotirasida:
ishchi serverda Django keshi bazada turadi, baza ishlamasa u ham ishlamaydi.

Manzil faqat ichki tarmoq uchun (Telegram bot monitoringi): Caddy uni tashqariga ochmaydi.
"""
import logging
import threading
import time

from django.db import connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

CACHE_SECONDS = 15

_lock = threading.Lock()
_cached = None
_cached_at = 0.0


def _database_ok():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception:  # noqa: BLE001
        logger.warning("Holat tekshiruvi: asosiy baza javob bermadi", exc_info=True)
        return False


def _lab_database_ok():
    from labs.sandbox import ping

    try:
        ping()
        return True
    except Exception:  # noqa: BLE001 — ulanish ham, so'rov ham xato berishi mumkin
        logger.warning("Holat tekshiruvi: laboratoriya bazasi javob bermadi")
        return False


def check():
    global _cached, _cached_at
    # Qulf: bir vaqtda kelgan so'rovlar bazalarni bittadan ortiq tekshirtirmaydi
    with _lock:
        if _cached is None or time.monotonic() - _cached_at >= CACHE_SECONDS:
            _cached = {"database": _database_ok(), "lab_database": _lab_database_ok()}
            _cached_at = time.monotonic()
        return dict(_cached)


def reset_cache():
    global _cached
    with _lock:
        _cached = None


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        result = check()
        ok = all(result.values())
        return Response({"ok": ok, **result}, status=status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE)
