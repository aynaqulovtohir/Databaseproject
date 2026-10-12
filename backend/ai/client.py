"""Anthropic API bilan ishlash: bitta joyda mijoz yaratish va xatolarni turlarga ajratish."""
import anthropic
from django.conf import settings

REQUEST_TIMEOUT_SECONDS = 120.0


class AIError(Exception):
    """AI bilan bog'liq barcha xatolar uchun asos."""


class AINotConfigured(AIError):
    """API kalit .env da ko'rsatilmagan."""


class AITransientError(AIError):
    """Vaqtinchalik xato (tarmoq, limit, server). Keyinroq qayta urinish mumkin."""


class AIPermanentError(AIError):
    """Qayta urinish foyda bermaydigan xato (noto'g'ri kalit, rad etish, noto'g'ri javob)."""


def is_configured():
    return bool(settings.ANTHROPIC_API_KEY)


def get_client():
    if not is_configured():
        raise AINotConfigured("ANTHROPIC_API_KEY .env faylida ko'rsatilmagan.")
    return anthropic.Anthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=2,
    )


def create_message(**params):
    """Modelga so'rov yuboradi va xatolarni o'zimizning turlarga o'tkazadi."""
    client = get_client()
    try:
        response = client.messages.create(model=settings.AI_MODEL, **params)
    except anthropic.AuthenticationError as exc:
        raise AIPermanentError("API kalit noto'g'ri yoki bekor qilingan.") from exc
    except anthropic.PermissionDeniedError as exc:
        raise AIPermanentError("API kalitda bu amal uchun ruxsat yo'q.") from exc
    except anthropic.NotFoundError as exc:
        raise AIPermanentError(f"AI modeli topilmadi: {settings.AI_MODEL}") from exc
    except anthropic.BadRequestError as exc:
        raise AIPermanentError(f"AI so'rovni qabul qilmadi: {exc.message}") from exc
    except anthropic.RateLimitError as exc:
        raise AITransientError("AI so'rovlar limiti oshdi.") from exc
    except anthropic.APIStatusError as exc:
        if exc.status_code >= 500:
            raise AITransientError(f"AI serverida xato ({exc.status_code}).") from exc
        raise AIPermanentError(f"AI xatosi ({exc.status_code}): {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise AITransientError("AI serveriga ulanib bo'lmadi.") from exc

    if response.stop_reason == "refusal":
        raise AIPermanentError("AI bu so'rovga javob berishdan bosh tortdi.")
    if response.stop_reason == "max_tokens":
        raise AIPermanentError("AI javobi juda uzun bo'lib, to'liq kelmadi.")
    return response


def extract_text(response):
    text = "".join(block.text for block in response.content if block.type == "text")
    if not text.strip():
        raise AIPermanentError("AI bo'sh javob qaytardi.")
    return text
