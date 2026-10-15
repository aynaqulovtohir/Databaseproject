"""Virtual laboratoriya API'lari."""
import logging
from datetime import datetime, time

from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from ai.client import AIError, AINotConfigured, AITransientError, is_configured
from learning.permissions import IsStaffRoleOrReadOnly
from users.models import User

from .access import visible_labs
from .advice import ai_grade, ai_grade_diagram, auto_grade, auto_grade_diagram, generate_advice
from .checker import LabSetupError, check_code
from .er import build_fixed, compare
from .models import Lab, LabAttempt, LabGrade
from .research import build_export
from .sandbox import SandboxUnavailable
from .serializers import (
    DiagramRunSerializer,
    LabSerializer,
    RunSerializer,
    StudentLabSerializer,
    fix_payload,
    grade_payload,
)

logger = logging.getLogger(__name__)


def ai_advice_left(student):
    """Talaba bugun yana nechta AI maslahati olishi mumkin."""
    today_start = timezone.make_aware(datetime.combine(timezone.localdate(), time.min))
    used = LabAttempt.objects.filter(student=student, ai_requested_at__gte=today_start).count()
    return max(0, settings.LAB_AI_DAILY_LIMIT - used)


def ai_grades_left(student):
    """Talaba bugun yana nechta topshirig'ini AI baholashi mumkin (undan keyin avtomatik baho)."""
    today_start = timezone.make_aware(datetime.combine(timezone.localdate(), time.min))
    used = LabAttempt.objects.filter(student=student, is_submission=True, created_at__gte=today_start).count()
    # Hozirgina saqlangan urinishning o'zi ham hisobga kirgan
    return settings.LAB_AI_GRADES_DAILY_LIMIT - used + 1


def grade_attempt(attempt):
    """Topshirilgan urinishni baholaydi: AI ishlasa AI, aks holda avtomatik. Qaytaradi: (ball, izoh, manba)."""
    if is_configured() and ai_grades_left(attempt.student) > 0:
        try:
            score, comment = ai_grade(attempt)
            return score, comment, LabGrade.Source.AI
        except AINotConfigured:
            pass
        except AIError as exc:
            logger.warning("Laboratoriya urinishi #%s: AI baholay olmadi, avtomatik baho qo'yildi: %s", attempt.pk, exc)
    score, comment = auto_grade(attempt)
    return score, comment, LabGrade.Source.AUTO


def grade_diagram_attempt(attempt, ratio):
    """Topshirilgan ER-diagrammani baholaydi; noto'g'ri bo'lsa, tuzatilgan diagramma va AI tushuntirishini saqlaydi."""
    fixed = None if attempt.is_correct else build_fixed(attempt.diagram, attempt.lab.reference_diagram)
    changes = fixed["changes"] if fixed else []
    result = None
    if is_configured() and ai_grades_left(attempt.student) > 0:
        try:
            score, comment, explanation = ai_grade_diagram(attempt, ratio, changes)
            result = score, comment, LabGrade.Source.AI
        except AINotConfigured:
            pass
        except AIError as exc:
            logger.warning("ER urinishi #%s: AI baholay olmadi, avtomatik baho qo'yildi: %s", attempt.pk, exc)
    if result is None:
        explanation = ""
        score, comment = auto_grade_diagram(attempt, ratio)
        result = score, comment, LabGrade.Source.AUTO
    if fixed:
        attempt.fixed_diagram = fixed
        attempt.fix_explanation = explanation
        attempt.save(update_fields=["fixed_diagram", "fix_explanation"])
    return result


class LabViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaffRoleOrReadOnly]
    # Faqat `run` amalida ishlatiladi (@action orqali beriladi)
    throttle_scope = None

    def get_queryset(self):
        user = self.request.user
        queryset = visible_labs(user).select_related("author")
        if user.is_student:
            own_attempts = LabAttempt.objects.filter(student=user).only(
                "lab_id", "is_correct", "sql_code", "diagram", "is_submission", "fixed_diagram", "fix_explanation"
            )
            return queryset.prefetch_related(
                Prefetch("attempts", queryset=own_attempts, to_attr="my_attempts"),
                Prefetch("grades", queryset=LabGrade.objects.filter(student=user), to_attr="my_grades"),
            )
        return queryset.prefetch_related("groups")

    def get_serializer_class(self):
        if self.request.user.is_student:
            return StudentLabSerializer
        return LabSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["include_last_code"] = self.action == "retrieve"
        return context

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def check(self, request, lab):
        """Kod yoki diagrammani tekshiradi.

        Qaytaradi: (natija, urinish ma'lumotlari) yoki xato bo'lsa (Response, None).
        """
        if lab.kind == Lab.Kind.ER:
            serializer = DiagramRunSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            diagram = serializer.validated_data["diagram"]
            comparison = compare(diagram, lab.reference_diagram)
            result = {
                "is_correct": not comparison["differences"],
                "error": None,
                "result": None,
                "status_message": "",
                "differences": comparison["differences"],
                "checked_against_solution": True,
            }
            return result, {"diagram": diagram, "ratio": comparison["ratio"]}

        serializer = RunSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sql_code = serializer.validated_data["sql_code"]
        try:
            return check_code(lab, sql_code), {"sql_code": sql_code}
        except SandboxUnavailable:
            logger.exception("Laboratoriya bazasiga ulanib bo'lmadi")
            return Response(
                {"detail": "Laboratoriya bazasi vaqtincha ishlamayapti. Birozdan keyin qayta urinib ko'ring."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            ), None
        except LabSetupError as exc:
            logger.error("Laboratoriya #%s sozlamasida xato: %s", lab.pk, exc)
            if request.user.is_student:
                detail = "Laboratoriya sozlamasida xato bor. O'qituvchiga xabar bering."
            else:
                detail = f"Laboratoriya sozlamasida xato ({exc.field}): {exc}"
            return Response({"detail": detail}, status=status.HTTP_409_CONFLICT), None

    @staticmethod
    def save_attempt(lab, student, payload, result, is_submission=False):
        return LabAttempt.objects.create(
            lab=lab,
            student=student,
            sql_code=payload.get("sql_code", ""),
            diagram=payload.get("diagram"),
            is_correct=result["is_correct"],
            feedback={"error": result["error"], "differences": result["differences"]},
            is_submission=is_submission,
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        throttle_classes=[ScopedRateThrottle],
        throttle_scope="lab_run",
    )
    def run(self, request, pk=None):
        """Kodni ishga tushirib tekshiradi. Talabaning har bir ishga tushirishi urinish sifatida saqlanadi."""
        lab = self.get_object()
        result, payload = self.check(request, lab)
        if payload is None:
            return result

        result["attempt_id"] = None
        result["ai_available"] = False
        if request.user.is_student:
            attempt = self.save_attempt(lab, request.user, payload, result)
            result["attempt_id"] = attempt.pk
            result["ai_available"] = (
                not result["is_correct"] and is_configured() and ai_advice_left(request.user) > 0
            )
        return Response(result)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        throttle_classes=[ScopedRateThrottle],
        throttle_scope="lab_submit",
    )
    def submit(self, request, pk=None):
        """Talaba kodni baholashga topshiradi: kod tekshiriladi va unga ball qo'yiladi.

        Qayta topshirish mumkin; talabaning bahosi sifatida eng yuqori ball saqlanadi.
        """
        if not request.user.is_student:
            raise PermissionDenied("Baholashga faqat talaba topshira oladi.")
        lab = self.get_object()
        result, payload = self.check(request, lab)
        if payload is None:
            return result

        attempt = self.save_attempt(lab, request.user, payload, result, is_submission=True)
        if lab.kind == Lab.Kind.ER:
            score, comment, source = grade_diagram_attempt(attempt, payload["ratio"])
            # Noto'g'ri diagramma: tuzatilgan variant faqat topshirilgandan keyin ko'rsatiladi
            result["fix"] = fix_payload(attempt)
        else:
            score, comment, source = grade_attempt(attempt)
        with transaction.atomic():
            best = LabGrade.objects.select_for_update().filter(lab=lab, student=request.user).first()
            if best is None:
                best = LabGrade.objects.create(
                    lab=lab, student=request.user, attempt=attempt, score=score, comment=comment, source=source
                )
            elif score >= best.score:
                best.attempt, best.score, best.comment, best.source = attempt, score, comment, source
                best.save()

        result["attempt_id"] = attempt.pk
        result["ai_available"] = (
            not result["is_correct"] and is_configured() and ai_advice_left(request.user) > 0
        )
        result["grade"] = {"score": score, "comment": comment, "source": source, "graded_at": attempt.created_at}
        result["best_grade"] = grade_payload(best)
        return Response(result)

    @action(detail=False, methods=["get"], url_path="research-export")
    def research_export(self, request):
        """Ilmiy tadqiqot uchun anonim ma'lumotlar (ZIP: laboratoriyalar va testlar natijalari, README.txt).

        Admin — barcha, o'qituvchi — o'z laboratoriyalari. ?lab=<id> bilan alohida laboratoriyalarni tanlash mumkin.
        """
        if request.user.is_student:
            raise PermissionDenied("Bu amal faqat admin yoki o'qituvchi uchun.")
        labs = visible_labs(request.user)
        lab_ids = request.query_params.getlist("lab")
        if lab_ids:
            if not all(lab_id.isdigit() for lab_id in lab_ids):
                raise ValidationError({"lab": "Laboratoriya raqami butun son bo'lishi kerak."})
            labs = labs.filter(pk__in=lab_ids)
        from quizzes.views import visible_quizzes

        filename = f"laboratoriya-tadqiqot-{timezone.localdate():%Y-%m-%d}.zip"
        response = HttpResponse(build_export(labs, visible_quizzes(request.user)), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=["get"])
    def progress(self, request, pk=None):
        """O'qituvchi uchun: laboratoriya berilgan guruhlardagi har bir talabaning holati."""
        if request.user.is_student:
            raise PermissionDenied("Bu amal faqat admin yoki o'qituvchi uchun.")
        lab = self.get_object()
        students = (
            User.objects.filter(role=User.Role.STUDENT, is_active=True, group__in=lab.groups.all())
            .select_related("group")
            .order_by("group__name", "last_name", "first_name", "id")
        )
        attempts_by_student = {}
        for attempt in LabAttempt.objects.filter(lab=lab).order_by("id"):
            attempts_by_student.setdefault(attempt.student_id, []).append(attempt)

        grades = {grade.student_id: grade for grade in LabGrade.objects.filter(lab=lab)}

        rows = []
        for student in students:
            attempts = attempts_by_student.get(student.pk, [])
            grade = grades.get(student.pk)
            correct = [attempt for attempt in attempts if attempt.is_correct]
            # Bajargan bo'lsa to'g'ri kodi, aks holda oxirgi urinishi ko'rsatiladi
            shown = (correct or attempts or [None])[-1]
            rows.append(
                {
                    "id": student.pk,
                    "first_name": student.first_name,
                    "last_name": student.last_name,
                    "group": student.group.name,
                    "attempts": len(attempts),
                    "solved": bool(correct),
                    "last_attempt_at": attempts[-1].created_at if attempts else None,
                    "code": shown.sql_code if shown else "",
                    "diagram": shown.diagram if shown else None,
                    "grade": grade_payload(grade) if grade else None,
                }
            )
        return Response(rows)


class LabAttemptAdviceView(APIView):
    """Xato urinish uchun AI maslahati. Faqat urinish egasi (talaba) so'ray oladi."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        attempt = get_object_or_404(LabAttempt.objects.select_related("lab"), pk=pk, student=request.user)
        if attempt.is_correct:
            raise ValidationError({"detail": "Bu urinish to'g'ri: maslahat kerak emas."})
        if attempt.ai_advice:
            return Response({"advice": attempt.ai_advice})
        if not is_configured():
            return Response(
                {"detail": "AI maslahatchi hali sozlanmagan."}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        if ai_advice_left(request.user) <= 0:
            return Response(
                {"detail": "Bugungi AI maslahatlari limiti tugadi. Ertaga yana urinib ko'ring."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            advice = generate_advice(attempt)
        except AITransientError:
            return Response(
                {"detail": "AI maslahatchi vaqtincha ishlamayapti. Birozdan keyin qayta urinib ko'ring."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except AIError as exc:
            logger.error("Laboratoriya maslahati xatosi: %s", exc)
            return Response(
                {"detail": "AI bu kod bo'yicha maslahat bera olmadi."}, status=status.HTTP_502_BAD_GATEWAY
            )

        # Faqat muvaffaqiyatli maslahat kunlik limitdan yechiladi
        attempt.ai_advice = advice
        attempt.ai_requested_at = timezone.now()
        attempt.save(update_fields=["ai_advice", "ai_requested_at"])
        return Response({"advice": advice})
