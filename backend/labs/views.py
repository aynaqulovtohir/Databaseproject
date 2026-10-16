"""Virtual laboratoriya API'lari."""
import logging
from collections import defaultdict

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
from .advice import MAX_HINT_LEVEL, ai_grade, ai_grade_diagram, auto_grade, auto_grade_diagram, generate_advice
from .checker import LabSetupError, check_code, try_code
from .mistakes import build_report
from .quota import (
    ai_advice_left,
    ai_error_response,
    ai_grades_left,
    ai_usable,
    record_ai_action,
    refuse_ai,
    sandbox_down_response,
)
from .er import build_fixed, compare
from .models import AIAction, BlindReview, Lab, LabAttempt, LabChatMessage, LabGrade
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


def grade_attempt(attempt):
    """Topshirilgan urinishni baholaydi: AI ishlasa AI, aks holda avtomatik. Qaytaradi: (ball, izoh, manba)."""
    if ai_usable(attempt.student) and ai_grades_left(attempt.student) > 0:
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
    if ai_usable(attempt.student) and ai_grades_left(attempt.student) > 0:
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
        return self.execute(request, lab, check_code, sql_code)

    @staticmethod
    def execute(request, lab, runner, sql_code):
        """`runner(lab, sql_code)` ni qum qutida bajaradi. Qaytaradi: (natija, ma'lumot) yoki (Response, None)."""
        try:
            return runner(lab, sql_code), {"sql_code": sql_code}
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
            ai_enabled=student.ai_allowed,
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
        result["ai_available"] = result["ai_explain"] = False
        if request.user.is_student:
            attempt = self.save_attempt(lab, request.user, payload, result)
            result["attempt_id"] = attempt.pk
            ai_left = ai_usable(request.user) and ai_advice_left(request.user) > 0
            result["ai_available"] = not result["is_correct"] and ai_left
            result["ai_explain"] = result["is_correct"] and ai_left
        return Response(result)

    @action(
        detail=True,
        methods=["post"],
        url_path="try",
        permission_classes=[IsAuthenticated],
        throttle_classes=[ScopedRateThrottle],
        throttle_scope="lab_try",
    )
    def try_run(self, request, pk=None):
        """Erkin sinash: kod bajariladi va natijasi ko'rsatiladi, lekin tekshirilmaydi va urinish hisoblanmaydi."""
        lab = self.get_object()
        if lab.kind != Lab.Kind.SQL:
            raise ValidationError({"detail": "Erkin sinash faqat SQL laboratoriyalarida bor."})
        serializer = RunSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result, payload = self.execute(request, lab, try_code, serializer.validated_data["sql_code"])
        return result if payload is None else Response(result)

    @action(
        detail=True,
        methods=["post"],
        url_path="explain-plan",
        permission_classes=[IsAuthenticated],
        throttle_classes=[ScopedRateThrottle],
        throttle_scope="lab_ai",
    )
    def explain_plan(self, request, pk=None):
        """Indeks laboratoriyasi: {sql_code, mode}. mode="explain" — rejaning AI tushuntirishi (indeks aytilmaydi);
        mode="suggest" — yechgan talabaga AI muqobil indeksi, qum qutida o'lchab solishtiriladi."""
        from .plan_ai import explain_plan, suggest_index

        lab = self.get_object()
        if lab.kind != Lab.Kind.SQL or not lab.plan_query.strip():
            raise ValidationError({"detail": "Reja tushuntirishi faqat indeks (EXPLAIN) laboratoriyasida bor."})
        mode = request.data.get("mode", "explain")
        if mode not in ("explain", "suggest"):
            raise ValidationError({"mode": "Rejim explain yoki suggest bo'lishi kerak."})
        serializer = RunSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if (
            mode == "suggest"
            and request.user.is_student
            and not LabAttempt.objects.filter(lab=lab, student=request.user, is_correct=True).exists()
        ):
            raise PermissionDenied("Muqobil indeks taklifi laboratoriyani to'g'ri yechgandan keyin ochiladi.")
        refused = refuse_ai(request.user)
        if refused:
            return refused
        runner = suggest_index if mode == "suggest" else explain_plan
        try:
            data = runner(lab, serializer.validated_data["sql_code"])
        except SandboxUnavailable:
            logger.exception("Laboratoriya bazasiga ulanib bo'lmadi")
            return sandbox_down_response()
        except AIError as exc:
            return ai_error_response(exc, "reja")
        record_ai_action(request.user, AIAction.Kind.PLAN_SUGGEST if mode == "suggest" else AIAction.Kind.PLAN_EXPLAIN)
        return Response(data)

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
        ai_left = ai_usable(request.user) and ai_advice_left(request.user) > 0
        result["ai_available"] = not result["is_correct"] and ai_left
        result["ai_explain"] = result["is_correct"] and ai_left
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

    def staff_labs(self, request):
        """Admin — barcha, o'qituvchi — o'z laboratoriyalari; ?lab=<id> bilan bittasi."""
        if request.user.is_student:
            raise PermissionDenied("Bu amal faqat admin yoki o'qituvchi uchun.")
        labs = visible_labs(request.user)
        lab_id = request.query_params.get("lab")
        if lab_id:
            if not lab_id.isdigit():
                raise ValidationError({"lab": "Laboratoriya raqami butun son bo'lishi kerak."})
            labs = labs.filter(pk=lab_id)
        return labs

    @action(
        detail=False,
        methods=["get", "post"],
        url_path="blind-review",
        throttle_classes=[ScopedRateThrottle],
        throttle_scope="blind_review",
    )
    def blind_review(self, request):
        """Ko'r baholash. GET — navbatdagi ish (talaba ismi va AI bahosisiz), POST {attempt, score} — baho.

        Baho bir marta qo'yiladi va o'zgartirilmaydi.
        """
        from .blind_review import item_payload, queue

        labs = self.staff_labs(request)
        if request.method == "GET":
            pending = queue(labs, request.user)
            reviewed = BlindReview.objects.filter(reviewer=request.user, attempt__lab__in=labs).count()
            return Response(
                {
                    "item": item_payload(pending[0]) if pending else None,
                    "remaining": len(pending),
                    "reviewed": reviewed,
                }
            )

        attempt_id, score = request.data.get("attempt"), request.data.get("score")
        if not isinstance(attempt_id, int) or isinstance(attempt_id, bool):
            raise ValidationError({"attempt": "Urinish raqami butun son bo'lishi kerak."})
        if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100:
            raise ValidationError({"score": "Ball 0 dan 100 gacha butun son bo'lsin."})
        # Faqat navbatdagi ishlar: o'z laboratoriyasidagi, hozir baho sifatida turgan urinish
        grade = LabGrade.objects.filter(lab__in=labs, attempt_id=attempt_id).first()
        if grade is None:
            raise ValidationError({"attempt": "Bu ish ko'r baholash navbatida yo'q."})
        review, created = BlindReview.objects.get_or_create(
            attempt_id=attempt_id,
            reviewer=request.user,
            defaults={"score": score, "ai_score": grade.score, "ai_source": grade.source},
        )
        if not created:
            return Response(
                {"detail": "Bu ishni allaqachon baholagansiz: ko'r baholash natijasi o'zgartirilmaydi."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response({"saved": True}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="blind-review/agreement")
    def blind_review_agreement(self, request):
        """AI va o'qituvchi baholari mosligi. O'qituvchi — o'zi baholagan ishlar, admin — hamma baholovchilar."""
        from .blind_review import agreement

        labs = self.staff_labs(request)
        return Response(agreement(labs, None if request.user.is_admin else request.user))

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        """Laboratoriyaning nusxasi: shart, SQL va namunaviy diagramma ko'chiriladi, urinishlar emas.

        O'qituvchining nusxasiga faqat o'zi o'qitadigan guruhlar o'tadi.
        """
        if request.user.is_student:
            raise PermissionDenied("Bu amal faqat admin yoki o'qituvchi uchun.")
        lab = self.get_object()
        groups = lab.groups.all()
        if request.user.is_teacher:
            groups = groups.filter(teachers=request.user)
        copy = Lab.objects.create(
            kind=lab.kind,
            title=f"{lab.title} (nusxa)"[: Lab._meta.get_field("title").max_length],
            description=lab.description,
            theory=lab.theory,
            setup_sql=lab.setup_sql,
            solution_sql=lab.solution_sql,
            hidden_setup_sql=lab.hidden_setup_sql,
            reference_diagram=lab.reference_diagram,
            given_diagram=lab.given_diagram,
            plan_query=lab.plan_query,
            plan_forbidden=lab.plan_forbidden,
            concurrent=lab.concurrent,
            author=request.user,
        )
        copy.groups.set(groups)
        return Response(LabSerializer(copy, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def mistakes(self, request, pk=None):
        """O'qituvchi uchun: eng ko'p uchraydigan xatolar (?group=<id> — bitta guruh bo'yicha)."""
        if request.user.is_student:
            raise PermissionDenied("Bu amal faqat admin yoki o'qituvchi uchun.")
        lab = self.get_object()
        groups = lab.groups.all()
        group_id = request.query_params.get("group")
        if group_id:
            if not group_id.isdigit():
                raise ValidationError({"group": "Guruh raqami butun son bo'lishi kerak."})
            groups = groups.filter(pk=group_id)
        student_ids = User.objects.filter(role=User.Role.STUDENT, is_active=True, group__in=groups).values_list(
            "pk", flat=True
        )
        attempts = LabAttempt.objects.filter(lab=lab).only("student_id", "is_correct", "feedback").order_by("id")
        return Response(build_report(attempts, student_ids))

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
            explained = [attempt for attempt in correct if attempt.explanation_verdict]
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
                    # Talaba yechimini o'z so'zlari bilan tushuntirgan bo'lsa — oxirgisi va AI bahosi
                    "explanation": (
                        {
                            "text": explained[-1].self_explanation,
                            "verdict": explained[-1].explanation_verdict,
                            "feedback": explained[-1].explanation_feedback,
                        }
                        if explained
                        else None
                    ),
                }
            )
        return Response(rows)


    @action(detail=True, methods=["get"])
    def similarity(self, request, pk=None):
        """O'qituvchi uchun: yechimlari shubhali darajada o'xshash talabalar juftliklari (ko'chirish belgisi)."""
        from .similarity import THRESHOLD, find_similar

        if request.user.is_student:
            raise PermissionDenied("Bu amal faqat admin yoki o'qituvchi uchun.")
        lab = self.get_object()
        students = {
            student.pk: student
            for student in User.objects.filter(
                role=User.Role.STUDENT, is_active=True, group__in=lab.groups.all()
            ).select_related("group")
        }
        attempts_by_student = defaultdict(list)
        for attempt in LabAttempt.objects.filter(lab=lab, student_id__in=students).order_by("created_at", "id"):
            attempts_by_student[attempt.student_id].append(attempt)
        pairs, compared = find_similar(lab, attempts_by_student)

        def work(student_id):
            attempts = attempts_by_student[student_id]
            final = ([attempt for attempt in attempts if attempt.is_correct] or attempts)[-1]
            student = students[student_id]
            return {
                "id": student.pk,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "group": student.group.name,
                "solved": any(attempt.is_correct for attempt in attempts),
                "code": final.sql_code,
                "diagram": final.diagram,
            }

        return Response(
            {
                "compared": compared,
                "threshold": THRESHOLD,
                "pairs": [
                    {**{key: value for key, value in pair.items() if key != "students"},
                     "students": [work(student_id) for student_id in pair["students"]]}
                    for pair in pairs
                ],
            }
        )


class LabAttemptAdviceView(APIView):
    """Xato urinish uchun bosqichma-bosqich AI maslahati. Faqat urinish egasi (talaba) so'ray oladi.

    {"level": n} bilan n-darajali maslahat so'raladi (darajalar ketma-ket olinadi); level berilmasa,
    olingan maslahatlar qaytariladi (hali bo'lmasa — 1-daraja).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        attempt = get_object_or_404(LabAttempt.objects.select_related("lab"), pk=pk, student=request.user)
        if attempt.is_correct:
            raise ValidationError({"detail": "Bu urinish to'g'ri: maslahat kerak emas."})
        if not request.user.ai_allowed:
            raise PermissionDenied("Guruhingizda AI yordamchisi o'chirilgan.")
        # Darajalar joriy etilishidan oldingi urinishlarda bitta maslahat saqlangan
        hints = list(attempt.ai_hints) or ([attempt.ai_advice] if attempt.ai_advice else [])
        level = request.data.get("level", max(1, len(hints)))
        if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= MAX_HINT_LEVEL:
            raise ValidationError({"level": f"Daraja 1 dan {MAX_HINT_LEVEL} gacha bo'lishi kerak."})
        if level <= len(hints):
            return Response(self.payload(hints))
        if level > len(hints) + 1:
            raise ValidationError({"level": "Avval oldingi darajadagi maslahatni oling."})
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
            advice = generate_advice(attempt, level, list(hints))
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
        hints.append(advice)
        attempt.ai_hints = hints
        attempt.ai_hint_level = len(hints)
        attempt.ai_advice = advice
        attempt.ai_requested_at = timezone.now()
        attempt.save(update_fields=["ai_hints", "ai_hint_level", "ai_advice", "ai_requested_at"])
        return Response(self.payload(hints))

    @staticmethod
    def payload(hints):
        return {"advice": hints[-1], "hints": hints, "level": len(hints), "max_level": MAX_HINT_LEVEL}


class LabAttemptExplainView(APIView):
    """To'g'ri urinishdan keyin: talaba yechimini o'z so'zlari bilan tushuntiradi {text}, AI mosligini baholaydi."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "lab_ai"
    MIN_LENGTH = 40
    MAX_LENGTH = 3000

    def post(self, request, pk):
        from .self_explain import evaluate_explanation

        attempt = get_object_or_404(LabAttempt.objects.select_related("lab"), pk=pk, student=request.user)
        if not attempt.is_correct:
            raise ValidationError({"detail": "Tushuntirish to'g'ri yechimdan keyin yoziladi."})
        text = request.data.get("text")
        if not isinstance(text, str) or len(text.strip()) < self.MIN_LENGTH:
            raise ValidationError({"text": f"Kamida {self.MIN_LENGTH} belgi yozing: yechim nima qiladi va nega shunday?"})
        if len(text) > self.MAX_LENGTH:
            raise ValidationError({"text": f"Tushuntirish {self.MAX_LENGTH} belgidan oshmasin."})
        refused = refuse_ai(request.user)
        if refused:
            return refused
        try:
            verdict, feedback = evaluate_explanation(attempt, text.strip())
        except AIError as exc:
            return ai_error_response(exc, "tushuntirish")
        attempt.self_explanation = text.strip()
        attempt.explanation_verdict = verdict
        attempt.explanation_feedback = feedback
        attempt.save(update_fields=["self_explanation", "explanation_verdict", "explanation_feedback"])
        record_ai_action(request.user, AIAction.Kind.SELF_EXPLAIN)
        return Response({"verdict": verdict, "feedback": feedback})


class LabChatView(APIView):
    """Laboratoriya murabbiyi (Sokrat usulidagi AI). GET — yozishma, POST {content, sql_code?, diagram?} — savol.

    Faqat talaba va faqat o'ziga ko'rinadigan laboratoriyada. Har bir savol umumiy kunlik AI limitidan yechiladi.
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "lab_ai"

    def get_throttles(self):
        # Yozishmani o'qish cheklanmaydi, faqat AI'ga savol yuborish
        return [ScopedRateThrottle()] if self.request.method == "POST" else []

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user.is_student:
            raise PermissionDenied("Murabbiy faqat talaba uchun.")
        if not request.user.ai_allowed:
            raise PermissionDenied("Guruhingizda AI yordamchisi o'chirilgan.")
        self.lab = get_object_or_404(visible_labs(request.user), pk=kwargs["pk"])

    def own_messages(self):
        return LabChatMessage.objects.filter(lab=self.lab, student=self.request.user)

    def payload(self):
        return {
            "messages": [
                {"id": message.pk, "role": message.role, "content": message.content, "created_at": message.created_at}
                for message in self.own_messages()
            ],
            "ai_left": ai_advice_left(self.request.user),
        }

    def get(self, request, pk):
        return Response(self.payload())

    def post(self, request, pk):
        from learning.retrieval import find_passages

        from .coach import HISTORY_LIMIT, coach_reply, work_block

        content = request.data.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValidationError({"content": "Savol matni bo'sh bo'lmasligi kerak."})
        if len(content) > 2000:
            raise ValidationError({"content": "Savol 2000 belgidan oshmasligi kerak."})
        sql_code, diagram = "", None
        if self.lab.kind == Lab.Kind.ER and request.data.get("diagram") is not None:
            serializer = DiagramRunSerializer(data={"diagram": request.data["diagram"]})
            serializer.is_valid(raise_exception=True)
            diagram = serializer.validated_data["diagram"]
        elif self.lab.kind != Lab.Kind.ER and request.data.get("sql_code"):
            serializer = RunSerializer(data={"sql_code": request.data["sql_code"]})
            serializer.is_valid(raise_exception=True)
            sql_code = serializer.validated_data["sql_code"]
        refused = refuse_ai(request.user)
        if refused:
            return refused

        recent = list(self.own_messages().order_by("-created_at", "-id")[:HISTORY_LIMIT])[::-1]
        history = [
            {"role": message.role, "content": work_block(message.content) if message.role == "user" else message.content}
            for message in recent
        ]
        try:
            answer = coach_reply(
                self.lab,
                history,
                content.strip(),
                sql_code=sql_code,
                diagram=diagram,
                passages=find_passages(request.user, content, self.lab.title),
            )
        except AIError as exc:
            return ai_error_response(exc, "savol")
        with transaction.atomic():
            LabChatMessage.objects.create(
                lab=self.lab, student=request.user, role=LabChatMessage.Role.USER, content=content.strip()
            )
            LabChatMessage.objects.create(
                lab=self.lab, student=request.user, role=LabChatMessage.Role.ASSISTANT, content=answer
            )
            record_ai_action(request.user, AIAction.Kind.LAB_CHAT)
        return Response(self.payload(), status=status.HTTP_201_CREATED)


class StatisticsView(APIView):
    """O'qituvchi statistikasi: ?group=<id> bilan bitta guruh, aks holda barcha ruxsat etilgan guruhlar."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .statistics import allowed_groups, build_statistics

        if request.user.is_student:
            raise PermissionDenied("Statistika faqat admin va o'qituvchi uchun.")
        group = None
        group_id = request.query_params.get("group")
        if group_id:
            if not group_id.isdigit():
                raise ValidationError({"group": "Guruh raqami butun son bo'lishi kerak."})
            group = get_object_or_404(allowed_groups(request.user), pk=group_id)
        return Response(build_statistics(request.user, group))
