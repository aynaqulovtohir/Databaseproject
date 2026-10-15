"""Navbatdagi tahlillarni bajaruvchi. Navbat sifatida bazaning o'zi ishlatiladi."""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .client import AIError, AITransientError, current_model
from .models import AIAnalysis
from .services import analyze_submission

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
# Shu vaqtdan uzoq "processing" holatida qolgan tahlil qotib qolgan deb hisoblanadi
STUCK_AFTER = timedelta(minutes=10)


def release_stuck_analyses():
    """Worker to'satdan to'xtab qolgan bo'lsa, yarim qolgan tahlillarni navbatga qaytaradi."""
    return AIAnalysis.objects.filter(
        status=AIAnalysis.Status.PROCESSING, started_at__lt=timezone.now() - STUCK_AFTER
    ).update(status=AIAnalysis.Status.PENDING)


def claim_next_analysis():
    """Navbatdagi bitta tahlilni band qiladi (ikki worker bittasini olmasligi uchun qulflanadi)."""
    with transaction.atomic():
        analysis = (
            AIAnalysis.objects.select_for_update(skip_locked=True)
            .filter(status=AIAnalysis.Status.PENDING)
            .order_by("created_at", "id")
            .first()
        )
        if analysis is None:
            return None
        analysis.status = AIAnalysis.Status.PROCESSING
        analysis.started_at = timezone.now()
        analysis.attempts += 1
        analysis.save(update_fields=["status", "started_at", "attempts"])
        return analysis


def process_next():
    """Bitta tahlilni bajaradi. Qaytaradi: True - ish bajarildi, False - navbat bo'sh."""
    analysis = claim_next_analysis()
    if analysis is None:
        return False

    submission = analysis.submission
    try:
        result, input_tokens, output_tokens = analyze_submission(submission)
    except AITransientError as exc:
        if analysis.attempts < MAX_ATTEMPTS:
            # Navbatga qaytariladi, keyinroq qayta uriniladi
            analysis.status = AIAnalysis.Status.PENDING
            analysis.error_message = str(exc)
            analysis.save(update_fields=["status", "error_message"])
            logger.warning("Tahlil #%s: vaqtinchalik xato, qayta uriniladi: %s", analysis.pk, exc)
        else:
            mark_failed(analysis, exc)
        return True
    except AIError as exc:
        mark_failed(analysis, exc)
        return True
    except Exception as exc:  # kutilmagan xato worker'ni to'xtatmasligi kerak
        logger.exception("Tahlil #%s: kutilmagan xato", analysis.pk)
        mark_failed(analysis, exc)
        return True

    analysis.status = AIAnalysis.Status.DONE
    analysis.summary = result.summary
    analysis.issues = [issue.model_dump() for issue in result.issues]
    analysis.recommendations = result.recommendations
    analysis.suggested_score = result.suggested_score
    analysis.score_rationale = result.score_rationale
    analysis.error_message = ""
    analysis.model_name = current_model()
    analysis.input_tokens = input_tokens
    analysis.output_tokens = output_tokens
    analysis.completed_at = timezone.now()
    analysis.save()
    logger.info("Tahlil #%s tayyor", analysis.pk)
    return True


def mark_failed(analysis, exc):
    analysis.status = AIAnalysis.Status.FAILED
    analysis.error_message = str(exc) or exc.__class__.__name__
    analysis.completed_at = timezone.now()
    analysis.save(update_fields=["status", "error_message", "completed_at"])
    logger.error("Tahlil #%s bajarilmadi: %s", analysis.pk, analysis.error_message)
