"""Telegram Bot API bilan ishlash (faqat kerakli amallar)."""
import requests
from django.conf import settings

API_URL = "https://api.telegram.org/bot{token}/{method}"


class TelegramError(Exception):
    """Telegram bilan bog'liq barcha xatolar uchun asos."""


class TelegramNotConfigured(TelegramError):
    """Bot tokeni yoki nomi .env da ko'rsatilmagan."""


class TelegramTransientError(TelegramError):
    """Vaqtinchalik xato (tarmoq, limit, server). Keyinroq qayta urinish mumkin."""


class TelegramBlockedError(TelegramError):
    """Foydalanuvchi botni bloklagan yoki chat mavjud emas."""


class TelegramPermanentError(TelegramError):
    """Qayta urinish foyda bermaydigan xato (masalan, token noto'g'ri)."""


def is_configured():
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_BOT_USERNAME)


def call(method, request_timeout=15, **params):
    """Bot API metodini chaqiradi va `result` qismini qaytaradi."""
    if not is_configured():
        raise TelegramNotConfigured("TELEGRAM_BOT_TOKEN yoki TELEGRAM_BOT_USERNAME ko'rsatilmagan.")

    url = API_URL.format(token=settings.TELEGRAM_BOT_TOKEN, method=method)
    try:
        response = requests.post(url, json=params, timeout=request_timeout)
        data = response.json()
    except (requests.RequestException, ValueError):
        # `from None`: asl xato matnida token bor URL bo'ladi, u log'ga tushmasligi kerak
        raise TelegramTransientError("Telegram serveriga ulanib bo'lmadi.") from None

    if data.get("ok"):
        return data.get("result")

    code = data.get("error_code")
    description = data.get("description", "")
    if code == 403 or (code == 400 and "chat not found" in description.lower()):
        raise TelegramBlockedError(description)
    if code == 429 or (code is not None and code >= 500):
        raise TelegramTransientError(description)
    raise TelegramPermanentError(f"{code}: {description}")


def send_message(chat_id, text):
    # parse_mode ishlatilmaydi: matn oddiy holda ketadi, maxsus belgilar muammo tug'dirmaydi
    return call("sendMessage", chat_id=chat_id, text=text)


def get_updates(offset=None, poll_seconds=10):
    params = {"timeout": poll_seconds, "allowed_updates": ["message"]}
    if offset is not None:
        params["offset"] = offset
    return call("getUpdates", request_timeout=poll_seconds + 10, **params)
