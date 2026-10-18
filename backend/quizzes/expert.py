"""Ekspert baholashi: test yoki so'rovnomaning mazmun validligi.

Har bir ekspert har bir savolni baholaydi:
- zarurligi (Lawshe, 1975): 3 — zarur, 2 — foydali, lekin zarur emas, 1 — keraksiz;
- mosligi (o'lchanadigan tushunchaga): 1-4 (4 — juda mos);
- aniqligi (tushunarli va bir ma'noli): 1-4.

Ko'rsatkichlar:
- CVR = (n_e − N/2) / (N/2), n_e — "zarur" deganlar. Kritik qiymat binomial taqsimotdan aniq hisoblanadi
  (bir tomonlama α = 0.05; Ayre & Scally, 2014): savol CVR ≥ CVR_krit bo'lsa, ekspertlar uni tasodifan emas,
  haqiqatan zarur deb hisoblagan;
- I-CVI — mosligini 3 yoki 4 deb baholaganlar ulushi; talab (Lynn, 1986): N ≤ 5 da 1.00, N ≥ 6 da ≥ 0.78;
- modifikatsiyalangan kappa k* = (I-CVI − P_c) / (1 − P_c), P_c = C(N, A) · 0.5^N — tasodifiy kelishuvni hisobga oladi
  (Polit, Beck & Owen, 2007): > 0.74 a'lo, 0.60-0.74 yaxshi, 0.40-0.59 qoniqarli;
- S-CVI/Ave — I-CVI lar o'rtachasi (≥ 0.90 talab), S-CVI/UA — hamma ekspert mos degan savollar ulushi (≥ 0.80).

Faqat yuborilgan (yakunlangan) baholar hisoblanadi.
"""
import hashlib
import secrets
from math import comb

from django.db import transaction
from django.utils import timezone

from .models import ExpertInvite, ExpertPanel, Question

ALPHA = 0.05
MIN_EXPERTS = 3
RECOMMENDED_EXPERTS = 5
S_CVI_AVE_TARGET = 0.90
S_CVI_UA_TARGET = 0.80
SCALES = {"essential": (1, 3), "relevance": (1, 4), "clarity": (1, 4)}
MAX_COMMENT = 1000
EXPERT_FIELDS = {"full_name": 200, "degree": 200, "position": 200, "workplace": 300, "experience_years": 3}
VERDICTS = {"keep": "Qoldirish", "revise": "Qayta ko'rib chiqish", "remove": "Olib tashlash"}


def new_token():
    """Havola tokeni va uning xeshi. Token faqat bir marta (yaratilganda) ko'rsatiladi."""
    token = secrets.token_urlsafe(32)
    return token, token_hash(token)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def snapshot(quiz):
    """Test savollarining nusxasi (ekspert shu versiyani baholaydi)."""
    items = []
    for number, question in enumerate(quiz.questions.prefetch_related("choices"), start=1):
        items.append(
            {
                "key": str(number),
                "order": number,
                "text": question.text,
                "kind": question.kind,
                "choices": []
                if question.kind == Question.Kind.LIKERT
                else [{"text": choice.text, "is_correct": choice.is_correct} for choice in question.choices.all()],
            }
        )
    return items


def create_invite(panel, label):
    token, digest = new_token()
    invite = ExpertInvite.objects.create(panel=panel, label=label, token_hash=digest)
    return invite, token


def renew_token(invite):
    token, digest = new_token()
    invite.token_hash = digest
    invite.save(update_fields=["token_hash", "updated_at"])
    return token


def find_invite(token):
    """Faol havola (bekor qilinmagan) yoki None."""
    if not isinstance(token, str) or not 20 <= len(token) <= 100:
        return None
    return ExpertInvite.objects.select_related("panel").filter(token_hash=token_hash(token), revoked=False).first()


class RatingsError(ValueError):
    pass


def clean_expert(raw):
    if not isinstance(raw, dict):
        raise RatingsError("Ekspert ma'lumotlari noto'g'ri formatda.")
    cleaned = {}
    for field, limit in EXPERT_FIELDS.items():
        value = raw.get(field, "")
        if field == "experience_years":
            if value in ("", None):
                cleaned[field] = None
                continue
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 70:
                raise RatingsError("Ish staji 0 dan 70 gacha butun son bo'lishi kerak.")
            cleaned[field] = value
            continue
        if not isinstance(value, str) or len(value) > limit:
            raise RatingsError(f"Ekspert ma'lumotidagi «{field}» maydoni {limit} belgidan oshmasin.")
        cleaned[field] = value.strip()
    return cleaned


def clean_ratings(panel, raw, complete):
    """{"<key>": {"essential", "relevance", "clarity", "comment"}}. complete — hamma savol baholangan bo'lishi shart."""
    if not isinstance(raw, dict):
        raise RatingsError("Baholar noto'g'ri formatda.")
    keys = {item["key"] for item in panel.items}
    cleaned = {}
    for key, value in raw.items():
        if key not in keys:
            raise RatingsError("Bunday savol yo'q.")
        if not isinstance(value, dict):
            raise RatingsError("Baholar noto'g'ri formatda.")
        item = {}
        for scale, (low, high) in SCALES.items():
            score = value.get(scale)
            if score is None:
                continue
            if not isinstance(score, int) or isinstance(score, bool) or not low <= score <= high:
                raise RatingsError(f"Baho {low} dan {high} gacha bo'lishi kerak.")
            item[scale] = score
        comment = value.get("comment", "")
        if not isinstance(comment, str) or len(comment) > MAX_COMMENT:
            raise RatingsError(f"Izoh {MAX_COMMENT} belgidan oshmasin.")
        item["comment"] = comment.strip()
        cleaned[key] = item
    if complete:
        missing = [item["order"] for item in panel.items if any(scale not in cleaned.get(item["key"], {}) for scale in SCALES)]
        if missing:
            raise RatingsError(f"Hamma savolni baholang. Baholanmagan: {', '.join(map(str, missing[:10]))}.")
    return cleaned


def save_ratings(invite, expert, ratings, submit):
    with transaction.atomic():
        invite = ExpertInvite.objects.select_for_update().get(pk=invite.pk)
        if invite.revoked:
            raise RatingsError("Havola bekor qilingan.")
        if invite.submitted_at:
            raise RatingsError("Baholar allaqachon yuborilgan.")
        invite.expert = clean_expert(expert)
        invite.ratings = clean_ratings(invite.panel, ratings, complete=submit)
        if submit:
            if not invite.expert.get("full_name"):
                raise RatingsError("Ism-familiyangizni kiriting: ekspertlar ro'yxati dissertatsiya ilovasida keltiriladi.")
            invite.submitted_at = timezone.now()
        invite.save()
    return invite


def cvr_critical(n, alpha=ALPHA):
    """Lawshe CVR ning kritik qiymati: P(X ≥ n_e | N, 0.5) ≤ α bo'ladigan eng kichik n_e uchun (Ayre & Scally, 2014)."""
    if n < 1:
        return None
    tail = 0.0
    critical = None
    for ne in range(n, -1, -1):
        tail += comb(n, ne) / 2**n
        if tail > alpha:
            break
        critical = ne
    if critical is None:
        return None  # N juda kichik: hatto hamma "zarur" desa ham tasodifdan farq qilmaydi
    return (critical - n / 2) / (n / 2)


def i_cvi_target(n):
    return 1.0 if n <= 5 else 0.78


def kappa_label(value):
    if value is None:
        return None
    if value > 0.74:
        return "a'lo"
    if value >= 0.60:
        return "yaxshi"
    if value >= 0.40:
        return "qoniqarli"
    return "past"


def _r(value, digits=2):
    return None if value is None else round(value, digits)


def results(panel):
    invites = list(panel.invites.all())
    submitted = [invite for invite in invites if invite.submitted_at]
    n = len(submitted)
    critical = cvr_critical(n) if n else None
    target = i_cvi_target(n) if n else None
    rows = []
    for item in panel.items:
        ratings = [invite.ratings.get(item["key"], {}) for invite in submitted]
        essential = sum(1 for rating in ratings if rating.get("essential") == 3)
        relevant = sum(1 for rating in ratings if rating.get("relevance", 0) >= 3)
        clarity = [rating["clarity"] for rating in ratings if "clarity" in rating]
        cvr = (essential - n / 2) / (n / 2) if n else None
        i_cvi = relevant / n if n else None
        kappa = None
        if n:
            chance = comb(n, relevant) * 0.5**n
            kappa = (i_cvi - chance) / (1 - chance) if chance < 1 else None
        # 5 tadan kam ekspertda CVR ni tasodifdan ajratib bo'lmaydi: hamma "zarur" deyishi talab qilinadi
        cvr_ok = cvr is not None and cvr >= (critical if critical is not None else 1.0) - 1e-9
        cvi_ok = i_cvi is not None and i_cvi >= target - 1e-9
        if n < MIN_EXPERTS:
            verdict = None
        elif cvr_ok and cvi_ok:
            verdict = "keep"
        elif cvr is not None and cvr <= 0 and not cvi_ok:
            verdict = "remove"
        else:
            verdict = "revise"
        rows.append(
            {
                "key": item["key"],
                "order": item["order"],
                "text": item["text"],
                "essential": essential,
                "cvr": _r(cvr),
                "cvr_ok": cvr_ok,
                "relevant": relevant,
                "i_cvi": _r(i_cvi),
                "i_cvi_ok": cvi_ok,
                "kappa": _r(kappa),
                "kappa_label": kappa_label(kappa),
                "clarity": _r(sum(clarity) / len(clarity)) if clarity else None,
                "verdict": {"key": verdict, "label": VERDICTS[verdict]} if verdict else None,
                "comments": [rating["comment"] for rating in ratings if rating.get("comment")],
            }
        )
    raw_cvi = [
        sum(1 for invite in submitted if invite.ratings.get(item["key"], {}).get("relevance", 0) >= 3) / n for item in panel.items
    ] if n else []
    s_cvi_ave = sum(raw_cvi) / len(raw_cvi) if raw_cvi else None
    s_cvi_ua = sum(1 for value in raw_cvi if value == 1) / len(raw_cvi) if raw_cvi else None
    cvr_values = [(row["essential"] - n / 2) / (n / 2) for row in rows] if n else []
    return {
        "experts": n,
        "invited": len(invites),
        "min_experts": MIN_EXPERTS,
        "recommended_experts": RECOMMENDED_EXPERTS,
        "cvr_critical": _r(critical),
        # Kritik qiymat yo'q (N < 5): hamma ekspert "zarur" deyishi kerak, CVR ning statistik ahamiyati tekshirilmaydi
        "cvr_testable": critical is not None,
        "i_cvi_target": target,
        "summary": {
            "cvi": _r(sum(cvr_values) / len(cvr_values)) if cvr_values else None,
            "s_cvi_ave": _r(s_cvi_ave),
            "s_cvi_ave_ok": s_cvi_ave is not None and s_cvi_ave >= S_CVI_AVE_TARGET,
            "s_cvi_ua": _r(s_cvi_ua),
            "s_cvi_ua_ok": s_cvi_ua is not None and s_cvi_ua >= S_CVI_UA_TARGET,
            "s_cvi_ave_target": S_CVI_AVE_TARGET,
            "s_cvi_ua_target": S_CVI_UA_TARGET,
            "keep": sum(1 for row in rows if row["verdict"] and row["verdict"]["key"] == "keep"),
            "revise": sum(1 for row in rows if row["verdict"] and row["verdict"]["key"] == "revise"),
            "remove": sum(1 for row in rows if row["verdict"] and row["verdict"]["key"] == "remove"),
        },
        "items": rows,
        "panel_experts": [
            {"label": invite.label, **{field: invite.expert.get(field) for field in EXPERT_FIELDS}, "submitted_at": invite.submitted_at}
            for invite in submitted
        ],
    }


def visible_panels(user):
    panels = ExpertPanel.objects.select_related("quiz", "author").prefetch_related("invites")
    return panels if user.is_admin else panels.filter(author=user)
