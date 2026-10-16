"""AI xizmati bilan ishlash: bitta joyda so'rov yuborish va xatolarni turlarga ajratish.

Ikki xizmat qo'llab-quvvatlanadi, qaysi biri ishlatilishi .env dagi AI_PROVIDER bilan tanlanadi:
- "anthropic" - Anthropic API (Claude);
- "gemini" - Google Gemini API.
Loyihaning qolgan qismi faqat `create_message` va `extract_text` ni chaqiradi.
"""
import logging
from types import SimpleNamespace

import anthropic
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Bu javoblarda keyingi zaxira model sinab ko'riladi: limit, server band yoki model olib tashlangan
GEMINI_RETRY_STATUSES = {404, 429, 500, 502, 503, 504}

REQUEST_TIMEOUT_SECONDS = 120.0
FALLBACK_TIMEOUT_SECONDS = 40.0


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


def current_model(fast=False):
    """Ishlatiladigan model nomi. fast=True — qisqa, ko'p so'raladigan javoblar (maslahatlar) uchun arzon model;
    u sozlanmagan bo'lsa, asosiy model ishlatiladi."""
    if uses_gemini():
        return (fast and settings.GEMINI_FAST_MODEL) or settings.GEMINI_MODEL
    return (fast and settings.AI_FAST_MODEL) or settings.AI_MODEL


# Keshdan o'qilgan va keshga yozilgan kirish tokenlari narxi oddiy kirish narxiga nisbatan (Anthropic tarifi)
CACHE_READ_PRICE_FACTOR = 0.1
CACHE_WRITE_PRICE_FACTOR = 1.25


def request_cost(fast, input_tokens, output_tokens, cache_read_tokens=0, cache_write_tokens=0):
    """So'rov narxi (AQSh dollari). Narx .env da berilmagan bo'lsa 0."""
    if fast and current_model(fast=True) != current_model():
        input_price, output_price = settings.AI_FAST_PRICE_INPUT_PER_MTOK, settings.AI_FAST_PRICE_OUTPUT_PER_MTOK
    else:
        input_price, output_price = settings.AI_PRICE_INPUT_PER_MTOK, settings.AI_PRICE_OUTPUT_PER_MTOK
    total = (
        input_tokens * input_price
        + cache_read_tokens * input_price * CACHE_READ_PRICE_FACTOR
        + cache_write_tokens * input_price * CACHE_WRITE_PRICE_FACTOR
        + output_tokens * output_price
    )
    return total / 1_000_000


def get_client():
    if not is_configured():
        raise AINotConfigured("ANTHROPIC_API_KEY .env faylida ko'rsatilmagan.")
    return anthropic.Anthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=2,
    )


def _record_usage(purpose, fast, response=None, error=None):
    """So'rov hisobini yozadi. Hisobni yozib bo'lmasa ham AI javobi talabaga yetkaziladi."""
    from .models import AIUsage

    try:
        usage = getattr(response, "usage", None)
        tokens = {
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
            "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "cache_write_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        }
        AIUsage.objects.create(
            purpose=purpose if purpose in AIUsage.Purpose.values else AIUsage.Purpose.OTHER,
            model_name=str(getattr(response, "model", "") or current_model(fast))[:100],
            cost=request_cost(fast, **tokens),
            **tokens,
            ok=error is None,
            error=f"{type(error).__name__}: {error}"[:200] if error else "",
        )
    except Exception:  # noqa: BLE001 — hisob yozilmasligi asosiy ishni to'xtatmasin
        logger.exception("AI so'rovi hisobini yozib bo'lmadi")


def create_message(purpose="other", fast=False, **params):
    """Modelga so'rov yuboradi, xatolarni o'zimizning turlarga o'tkazadi va so'rov hisobini yozadi.

    purpose — so'rov maqsadi (AIUsage.Purpose): xarajat hisobotida shu bo'yicha ajratiladi.
    fast — arzon va tez model (AI_FAST_MODEL): bosqichli maslahatlar kabi qisqa javoblar uchun.
    Parametrlar Anthropic API ko'rinishida beriladi (system, messages, max_tokens,
    output_config); Gemini tanlangan bo'lsa, ular shu yerda Gemini ko'rinishiga o'tkaziladi.
    """
    if not is_configured():
        raise AINotConfigured("AI uchun API kalit .env faylida ko'rsatilmagan.")
    model = current_model(fast)
    try:
        if uses_gemini():
            response = _create_gemini_message(model, **params)
        else:
            response = _create_anthropic_message(model, **params)
    except AIError as exc:
        _record_usage(purpose, fast, error=exc)
        raise
    _record_usage(purpose, fast, response)
    return response


def _cached_system(system):
    """Tizim ko'rsatmasi har bir so'rovda bir xil, o'zgaruvchan qism (talaba kodi) esa messages ichida:
    belgi tizim ko'rsatmasi oxiriga qo'yiladi va keyingi so'rovlar uni keshdan arzonroq o'qiydi.
    Ko'rsatma modelning eng kichik keshlanadigan hajmidan qisqa bo'lsa, shunchaki keshlanmaydi."""
    return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]


def _create_anthropic_message(model, **params):
    client = get_client()
    if isinstance(params.get("system"), str):
        params["system"] = _cached_system(params["system"])
    try:
        response = client.messages.create(model=model, **params)
    except anthropic.AuthenticationError as exc:
        raise AIPermanentError("API kalit noto'g'ri yoki bekor qilingan.") from exc
    except anthropic.PermissionDeniedError as exc:
        raise AIPermanentError("API kalitda bu amal uchun ruxsat yo'q.") from exc
    except anthropic.NotFoundError as exc:
        raise AIPermanentError(f"AI modeli topilmadi: {model}") from exc
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


def _gemini_models(primary):
    """Navbat bilan sinaladigan modellar: tanlangan model, keyin takrorlanmaydigan zaxiralar."""
    models = [primary]
    models += [model for model in [settings.GEMINI_MODEL, *settings.GEMINI_FALLBACK_MODELS] if model not in models]
    return models


def _post_gemini(primary, body):
    """So'rovni tanlangan modelga yuboradi; model band yoki mavjud bo'lmasa, keyingi zaxira modelga.

    Qaytaradi: (javob, model nomi). Oxirgi modelning javobi qanday bo'lsa, shunday qaytariladi.
    """
    models = _gemini_models(primary)
    for index, model in enumerate(models):
        is_last = index == len(models) - 1
        try:
            response = requests.post(
                GEMINI_URL.format(model=model),
                headers={"x-goog-api-key": settings.GEMINI_API_KEY},
                json=body,
                # Zaxira bor bo'lsa, osilib qolgan modelni uzoq kutmasdan keyingisiga o'tiladi
                timeout=REQUEST_TIMEOUT_SECONDS if is_last else FALLBACK_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            if is_last:
                raise AITransientError("AI serveriga ulanib bo'lmadi.") from exc
            logger.warning("Gemini %s javob bermadi, zaxira modelga o'tiladi: %s", model, exc)
            continue
        if is_last or response.status_code not in GEMINI_RETRY_STATUSES:
            return response, model
        logger.warning("Gemini %s band (%s), zaxira modelga o'tiladi.", model, response.status_code)


def _create_gemini_message(primary, *, max_tokens, system, messages, output_config=None):
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

    response, model = _post_gemini(primary, body)
    if response.status_code == 429:
        raise AITransientError("AI so'rovlar limiti oshdi.")
    if response.status_code >= 500:
        raise AITransientError(f"AI serverida xato ({response.status_code}).")
    if response.status_code == 404:
        raise AIPermanentError(f"AI modeli topilmadi: {model}")
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
    # Gemini takrorlangan boshlanishni o'zi keshlaydi; keshdan o'qilgani promptTokenCount ichida ham bor
    cached = usage.get("cachedContentTokenCount", 0)
    return SimpleNamespace(
        model=model,
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason="end_turn",
        usage=SimpleNamespace(
            cache_read_input_tokens=cached,
            input_tokens=usage.get("promptTokenCount", 0) - cached,
            output_tokens=usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0),
        ),
    )


def extract_text(response):
    text = "".join(block.text for block in response.content if block.type == "text")
    if not text.strip():
        raise AIPermanentError("AI bo'sh javob qaytardi.")
    return text
