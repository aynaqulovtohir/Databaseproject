"""AI xizmati bilan ishlash: bitta joyda so'rov yuborish va xatolarni turlarga ajratish.

Ikki xizmat qo'llab-quvvatlanadi, qaysi biri ishlatilishi .env dagi AI_PROVIDER bilan tanlanadi:
- "anthropic" - Anthropic API (Claude);
- "gemini" - Google Gemini API.
Loyihaning qolgan qismi faqat `create_message` va `extract_text` ni chaqiradi.
"""
from types import SimpleNamespace

import anthropic
import requests
from django.conf import settings

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

REQUEST_TIMEOUT_SECONDS = 120.0


class AIError(Exception):
    """AI bilan bog'liq barcha xatolar uchun asos."""


class AINotConfigured(AIError):
    """API kalit .env da ko'rsatilmagan."""


class AITransientError(AIError):
    """Vaqtinchalik xato (tarmoq, limit, server). Keyinroq qayta urinish mumkin."""


class AIPermanentError(AIError):
    """Qayta urinish foyda bermaydigan xato (noto'g'ri kalit, rad etish, noto'g'ri javob)."""


def uses_gemini():
    return settings.AI_PROVIDER == "gemini"


def is_configured():
    return bool(settings.GEMINI_API_KEY if uses_gemini() else settings.ANTHROPIC_API_KEY)


def current_model():
    """Hozir ishlatilayotgan model nomi (statistika uchun saqlanadi)."""
    return settings.GEMINI_MODEL if uses_gemini() else settings.AI_MODEL


def get_client():
    if not is_configured():
        raise AINotConfigured("ANTHROPIC_API_KEY .env faylida ko'rsatilmagan.")
    return anthropic.Anthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=2,
    )


def create_message(**params):
    """Modelga so'rov yuboradi va xatolarni o'zimizning turlarga o'tkazadi.

    Parametrlar Anthropic API ko'rinishida beriladi (system, messages, max_tokens,
    output_config); Gemini tanlangan bo'lsa, ular shu yerda Gemini ko'rinishiga o'tkaziladi.
    """
    if uses_gemini():
        return _create_gemini_message(**params)
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


def _to_gemini_schema(schema):
    """JSON Schema'ni Gemini qabul qiladigan ko'rinishga o'tkazadi (tur nomlari katta harfda)."""
    if isinstance(schema, list):
        return [_to_gemini_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    converted = {}
    for key, value in schema.items():
        if key == "additionalProperties":
            continue  # Gemini bu kalitni qabul qilmaydi
        if key == "type" and isinstance(value, str):
            converted[key] = value.upper()
        elif key == "properties":
            converted[key] = {name: _to_gemini_schema(item) for name, item in value.items()}
        elif key in ("enum", "required"):
            converted[key] = value
        else:
            converted[key] = _to_gemini_schema(value)
    return converted


def _gemini_error_message(response):
    try:
        return response.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        return response.text[:300]


def _create_gemini_message(*, max_tokens, system, messages, output_config=None):
    if not is_configured():
        raise AINotConfigured("GEMINI_API_KEY .env faylida ko'rsatilmagan.")

    generation_config = {"maxOutputTokens": max_tokens}
    response_format = (output_config or {}).get("format")
    if response_format:
        generation_config["responseMimeType"] = "application/json"
        generation_config["responseSchema"] = _to_gemini_schema(response_format["schema"])
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [
            {
                "role": "model" if message["role"] == "assistant" else "user",
                "parts": [{"text": message["content"]}],
            }
            for message in messages
        ],
        "generationConfig": generation_config,
    }

    try:
        response = requests.post(
            GEMINI_URL.format(model=settings.GEMINI_MODEL),
            headers={"x-goog-api-key": settings.GEMINI_API_KEY},
            json=body,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise AITransientError("AI serveriga ulanib bo'lmadi.") from exc

    if response.status_code == 429:
        raise AITransientError("AI so'rovlar limiti oshdi.")
    if response.status_code >= 500:
        raise AITransientError(f"AI serverida xato ({response.status_code}).")
    if response.status_code == 404:
        raise AIPermanentError(f"AI modeli topilmadi: {settings.GEMINI_MODEL}")
    if response.status_code in (401, 403):
        raise AIPermanentError("API kalit noto'g'ri yoki bu amal uchun ruxsat yo'q.")
    if response.status_code != 200:
        message = _gemini_error_message(response)
        if "API key" in message:
            raise AIPermanentError("API kalit noto'g'ri yoki bekor qilingan.")
        raise AIPermanentError(f"AI so'rovni qabul qilmadi: {message}")

    try:
        data = response.json()
    except ValueError as exc:
        raise AIPermanentError("AI javobini o'qib bo'lmadi.") from exc

    candidates = data.get("candidates") or []
    if not candidates:
        # Savolning o'zi xavfsizlik filtri tomonidan to'xtatilgan
        raise AIPermanentError("AI bu so'rovga javob berishdan bosh tortdi.")
    candidate = candidates[0]
    finish_reason = candidate.get("finishReason", "STOP")
    if finish_reason == "MAX_TOKENS":
        raise AIPermanentError("AI javobi juda uzun bo'lib, to'liq kelmadi.")
    parts = (candidate.get("content") or {}).get("parts") or []
    # "thought" belgili qismlar modelning ichki mulohazasi, javob emas
    text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
    if finish_reason != "STOP" and not text.strip():
        raise AIPermanentError("AI bu so'rovga javob berishdan bosh tortdi.")

    usage = data.get("usageMetadata") or {}
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason="end_turn",
        usage=SimpleNamespace(
            input_tokens=usage.get("promptTokenCount", 0),
            output_tokens=usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0),
        ),
    )


def extract_text(response):
    text = "".join(block.text for block in response.content if block.type == "text")
    if not text.strip():
        raise AIPermanentError("AI bo'sh javob qaytardi.")
    return text
