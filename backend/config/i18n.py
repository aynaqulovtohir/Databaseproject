"""Server xabarlarini foydalanuvchi tanlagan tilga o'girish: o'zbekcha (asosiy), inglizcha, ruscha.

Frontenddagi src/lib/i18n.ts bilan bir xil yondashuv: kalit — koddagi o'zbekcha asl matn,
tarjimalar locale/{en,ru}.json da. Til so'rovning Accept-Language sarlavhasidan
LocaleMiddleware orqali aniqlanadi; so'rovdan tashqarida (AI ishchisi, buyruqlar) o'zbekcha qoladi.
Tarjimasi yo'q matn o'zbekcha qaytadi, shuning uchun yangi xabar qo'shilsa hech narsa buzilmaydi.

    tr("Laboratoriya topilmadi.")
    tr("{count} ta savol", count=5)
"""

import json
import re
from functools import lru_cache
from pathlib import Path

from django.utils.translation import get_language

LOCALE_DIR = Path(__file__).resolve().parent.parent / "locale"
LANGS = ("uz", "en", "ru")
# "Kirish@@tizimga": @@ dan keyingi qism faqat bir xil so'zning ma'nolarini ajratadi, ko'rsatilmaydi
CONTEXT = "@@"
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


@lru_cache(maxsize=None)
def dictionary(lang: str) -> dict[str, str]:
    if lang == "uz":
        return {}
    path = LOCALE_DIR / f"{lang}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def current_lang() -> str:
    """Joriy so'rov tili: uz, en yoki ru (boshqa har qanday qiymat — uz)."""
    lang = (get_language() or "uz").split("-")[0]
    return lang if lang in LANGS else "uz"


def tr(text: str, /, **params) -> str:
    """Matnni joriy tilga o'giradi va {nomi} o'rinlarini params bilan to'ldiradi."""
    template = dictionary(current_lang()).get(text) or text.split(CONTEXT)[0]
    if not params:
        return template
    # str.format emas: matndagi boshqa jingalak qavslar ({, }) xato bermasin, atributga kirib bo'lmasin
    return _PLACEHOLDER.sub(lambda m: str(params[m[1]]) if m[1] in params else m[0], template)


def N_(text: str) -> str:
    """Modul darajasidagi matnni lug'atga belgilaydi, o'zini o'zgartirmaydi (gettext_noop kabi).
    Bunday matn javobda LocalizedJSONRenderer orqali o'giriladi."""
    return text


# AI ko'rsatmalaridagi "o'zbek tilida (lotin yozuvida) yoz" — foydalanuvchi tanlagan tilga almashtiriladi
_PROMPT_LANGUAGE = re.compile(r"[Oo]'zbek tilida \(lotin yozuvida\)")
PROMPT_LANGUAGES = {"en": "ingliz tilida (in English)", "ru": "rus tilida (на русском языке)"}


def localize_prompt(prompt: str, lang: str | None = None) -> str:
    """AI javobi so'rov tilida bo'lishi uchun ko'rsatmadagi til nomini almashtiradi (o'zbekchada o'zgarmaydi)."""
    name = PROMPT_LANGUAGES.get(lang or current_lang())
    if not name:
        return prompt
    return _PROMPT_LANGUAGE.sub(lambda m: name[0].upper() + name[1:] if m[0][0] == "O" else name, prompt)


# --- Saqlangan yoki tayyor o'zbekcha matnni javobda o'girish -------------------------------------------------
#
# Laboratoriya tekshiruvi natijalari bazaga o'zbekcha saqlanadi (xatolar hisoboti ularni matni bo'yicha guruhlaydi,
# tillar aralashib ketmasin). Javob chiqishida LocalizedJSONRenderer satrlarni lug'at bo'yicha o'giradi:
# aniq mos kelsa — to'g'ridan-to'g'ri, {o'rin}li andozaga mos kelsa — o'rinlar ajratib olinib qayta qo'yiladi.

# Foydalanuvchi yozgan matn va kod: tasodifan lug'atdagi so'zga teng bo'lsa ham o'zgarmasin
SKIP_FIELDS = frozenset({
    "sql_code", "code", "solution_sql", "setup_sql", "hidden_setup_sql", "starter_sql", "plan_query", "username",
    "first_name", "last_name", "full_name", "content", "answer", "answers", "justification", "explanation",
    "diagram", "reference_diagram", "given_diagram", "text", "comment", "question", "description", "theory",
    "email", "token", "rows", "columns", "result",
    # Laboratoriya, test, topshiriq nomlari: tahrirlash oynasida o'girilgan nom saqlanib ketmasin
    "title",
})
MAX_TEMPLATE_INPUT = 600
MIN_TEMPLATE_LETTERS = 6


def _compile_template(key: str, index: int):
    parts = _PLACEHOLDER.split(key)  # [matn, nom, matn, nom, ...]
    literal = "".join(parts[0::2])
    if sum(ch.isalpha() for ch in literal) < MIN_TEMPLATE_LETTERS:
        return None
    pattern, names = "", []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            pattern += re.escape(part)
        else:
            group = f"t{index}_{len(names)}"
            names.append((group, part))
            pattern += f"(?P<{group}>.+?)"
    return f"(?P<t{index}>{pattern})", names, parts[0][:3]


@lru_cache(maxsize=None)
def _templates(lang: str):
    """Andozalar birinchi 3 harfi bo'yicha guruhlanadi: har bir satr faqat mos guruh bilan solishtiriladi."""
    buckets: dict[str, list] = {}
    meta = {}
    for index, key in enumerate(dictionary(lang)):
        if "{" not in key:
            continue
        compiled = _compile_template(key, index)
        if not compiled:
            continue
        pattern, names, prefix = compiled
        meta[f"t{index}"] = (key, names)
        buckets.setdefault(prefix if len(prefix) == 3 else "", []).append(pattern)
    regexes = {prefix: re.compile("|".join(patterns), re.DOTALL) for prefix, patterns in buckets.items()}
    return regexes, meta


def translate_text(text: str, lang: str | None = None) -> str:
    """Tayyor o'zbekcha matnni (o'rinlari to'ldirilgan) tanlangan tilga o'giradi; topilmasa — o'zi."""
    lang = lang or current_lang()
    if lang == "uz" or not text:
        return text
    words = dictionary(lang)
    found = words.get(text)
    if found:
        return found
    if len(text) > MAX_TEMPLATE_INPUT or " " not in text:
        return text
    regexes, meta = _templates(lang)
    for prefix in (text[:3], ""):
        regex = regexes.get(prefix)
        match = regex.fullmatch(text) if regex else None
        if match:
            group = next(name for name, value in match.groupdict().items() if value is not None and "_" not in name)
            key, names = meta[group]
            params = {name: words.get(match[g], match[g]) for g, name in names}
            return tr_in(lang, key, **params)
    return text


def tr_in(lang: str, text: str, /, **params) -> str:
    template = dictionary(lang).get(text) or text.split(CONTEXT)[0]
    return _PLACEHOLDER.sub(lambda m: str(params[m[1]]) if m[1] in params else m[0], template)


def localize(data, lang: str | None = None):
    """Javob ma'lumotidagi barcha satrlarni o'giradi (SKIP_FIELDS dagi foydalanuvchi matnidan tashqari)."""
    lang = lang or current_lang()
    if lang == "uz":
        return data
    if isinstance(data, str):
        return translate_text(data, lang)
    if isinstance(data, list):
        return [localize(item, lang) for item in data]
    if isinstance(data, dict):
        return {key: value if key in SKIP_FIELDS else localize(value, lang) for key, value in data.items()}
    return data
