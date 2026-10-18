"""Testlar API'lari."""
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from learning.access import filter_visible
from learning.permissions import IsStaffRoleOrReadOnly
from users.models import User

from .models import Choice, Question, Quiz, QuizAttempt
from .serializers import QuizSerializer, StudentQuizSerializer
from .services import (
    AnswersError,
    attempt_status,
    clean_answers,
    finalize,
    finalize_if_expired,
    percent,
    result_payload,
    survey_summary,
    taking_payload,
)


def visible_quizzes(user):
    return filter_visible(Quiz.objects.all(), user)


class QuizViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaffRoleOrReadOnly]
    throttle_scope = None

    def get_queryset(self):
        questions = Question.objects.prefetch_related(Prefetch("choices", queryset=Choice.objects.order_by("order", "id")))
        return (
            visible_quizzes(self.request.user)
            .select_related("author")
            .prefetch_related("groups", Prefetch("questions", queryset=questions))
        )

    def get_serializer_class(self):
        return StudentQuizSerializer if self.request.user.is_student else QuizSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.user.is_authenticated and self.request.user.is_student:
            # Talabaning o'z topshirishlari (vaqti tugaganlari shu yerda yakunlanadi)
            attempts = QuizAttempt.objects.filter(student=self.request.user).select_related("quiz")
            context["attempts"] = {attempt.quiz_id: finalize_if_expired(attempt) for attempt in attempts}
        return context

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def destroy(self, request, *args, **kwargs):
        quiz = self.get_object()
        if quiz.attempts.filter(submitted_at__isnull=False).exists():
            raise ValidationError(
                {"detail": "Bu testni talabalar topshirgan: tadqiqot natijalari yo'qolmasligi uchun uni o'chirib bo'lmaydi."}
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        """Test nusxasi: savollar va variantlar ko'chiriladi, topshirishlar emas. {"kind"} bilan turi o'zgartiriladi —
        masalan, chiqish testidan o'sha savollar bilan kechiktirilgan test. O'qituvchining nusxasiga faqat
        o'zi o'qitadigan guruhlar o'tadi; ochilish/yopilish vaqtlari ko'chirilmaydi (yangidan belgilanadi)."""
        if request.user.is_student:
            raise PermissionDenied("Bu amal faqat admin yoki o'qituvchi uchun.")
        quiz = self.get_object()
        kind = request.data.get("kind", quiz.kind)
        if kind not in Quiz.Kind.values:
            raise ValidationError({"kind": "Noma'lum test turi."})
        if (kind == Quiz.Kind.SURVEY) != (quiz.kind == Quiz.Kind.SURVEY):
            raise ValidationError({"kind": "So'rovnomani oddiy testga (yoki aksincha) aylantirib bo'lmaydi."})
        groups = quiz.groups.all()
        if request.user.is_teacher:
            groups = groups.filter(teachers=request.user)
        suffix = f" — {Quiz.Kind(kind).label.lower()}" if kind != quiz.kind else " (nusxa)"
        copy = Quiz.objects.create(
            kind=kind,
            title=f"{quiz.title}{suffix}"[: Quiz._meta.get_field("title").max_length],
            description=quiz.description,
            author=request.user,
            time_limit_minutes=quiz.time_limit_minutes,
            show_answers=quiz.show_answers,
        )
        copy.groups.set(groups)
        for question in quiz.questions.all():
            choices = list(question.choices.all())
            question.pk = None
            question.quiz = copy
            question.save()
            Choice.objects.bulk_create(
                Choice(question=question, order=choice.order, text=choice.text, is_correct=choice.is_correct) for choice in choices
            )
        return Response(QuizSerializer(self.get_queryset().get(pk=copy.pk), context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED)

    # ---------- Talaba ----------

    def student_attempt(self, request):
        if not request.user.is_student:
            raise PermissionDenied("Testni faqat talaba topshiradi.")
        quiz = self.get_object()
        attempt = QuizAttempt.objects.filter(quiz=quiz, student=request.user).first()
        return quiz, finalize_if_expired(attempt)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def start(self, request, pk=None):
        """Testni boshlaydi (yoki boshlangan testga qaytaradi): savollar to'g'ri javoblarsiz beriladi."""
        quiz, attempt = self.student_attempt(request)
        if attempt and attempt.submitted_at:
            return Response(
                {"detail": "Siz bu testni topshirgansiz.", "result": result_payload(attempt)},
                status=status.HTTP_409_CONFLICT,
            )
        if attempt is None:
            if not quiz.is_open():
                raise ValidationError({"detail": "Test hozir yopiq."})
            attempt, _ = QuizAttempt.objects.get_or_create(quiz=quiz, student=request.user)
        return Response(taking_payload(attempt))

    @action(
        detail=True,
        methods=["put"],
        permission_classes=[IsAuthenticated],
        throttle_classes=[ScopedRateThrottle],
        throttle_scope="quiz_save",
    )
    def answers(self, request, pk=None):
        """Javoblarni oraliq saqlash (talaba belgilagan sayin)."""
        quiz, attempt = self.student_attempt(request)
        if attempt is None:
            raise ValidationError({"detail": "Avval testni boshlang."})
        if attempt.submitted_at:
            return Response(
                {"detail": "Vaqt tugadi: test yakunlandi.", "result": result_payload(attempt)},
                status=status.HTTP_409_CONFLICT,
            )
        attempt.answers = self.cleaned(quiz, request)
        attempt.save(update_fields=["answers"])
        return Response({"saved_at": timezone.now()})

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def submit(self, request, pk=None):
        """Testni yakunlaydi. Vaqt tugagan bo'lsa, yangi javoblar qabul qilinmaydi (saqlanganlari baholanadi)."""
        quiz, attempt = self.student_attempt(request)
        if attempt is None:
            raise ValidationError({"detail": "Avval testni boshlang."})
        if not attempt.submitted_at and "answers" in request.data:
            attempt.answers = self.cleaned(quiz, request)
            attempt.save(update_fields=["answers"])
        return Response(result_payload(finalize(attempt)))

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def result(self, request, pk=None):
        quiz, attempt = self.student_attempt(request)
        if attempt is None or not attempt.submitted_at:
            raise ValidationError({"detail": "Test hali topshirilmagan."})
        return Response(result_payload(attempt))

    @staticmethod
    def cleaned(quiz, request):
        try:
            return clean_answers(quiz, request.data.get("answers", {}))
        except AnswersError as exc:
            raise ValidationError({"answers": str(exc)})

    # ---------- O'qituvchi ----------

    @action(detail=True, methods=["get"])
    def survey(self, request, pk=None):
        """So'rovnoma bo'yicha umumlashgan natija (alohida talabalar javobisiz)."""
        if request.user.is_student:
            raise PermissionDenied("Bu amal faqat admin yoki o'qituvchi uchun.")
        quiz = self.get_object()
        if quiz.kind != Quiz.Kind.SURVEY:
            raise ValidationError({"detail": "Bu test so'rovnoma emas."})
        return Response(survey_summary(quiz))

    @action(detail=True, methods=["get"])
    def analysis(self, request, pk=None):
        """Psixometrik tahlil: test — KR-20/α, savollar qiyinligi, ajrata olish va variantlar; so'rovnoma — α."""
        from .psychometrics import analyse_quiz

        if request.user.is_student:
            raise PermissionDenied("Bu amal faqat admin yoki o'qituvchi uchun.")
        return Response(analyse_quiz(self.get_object()))

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        """Test berilgan guruhlardagi har bir talabaning natijasi."""
        if request.user.is_student:
            raise PermissionDenied("Bu amal faqat admin yoki o'qituvchi uchun.")
        quiz = self.get_object()
        attempts = {
            attempt.student_id: finalize_if_expired(attempt)
            for attempt in QuizAttempt.objects.filter(quiz=quiz).select_related("quiz")
        }
        students = (
            User.objects.filter(role=User.Role.STUDENT, is_active=True, group__in=quiz.groups.all())
            .select_related("group")
            .order_by("group__name", "last_name", "first_name", "id")
        )
        rows = []
        for student in students:
            attempt = attempts.get(student.pk)
            submitted = bool(attempt and attempt.submitted_at)
            rows.append(
                {
                    "id": student.pk,
                    "first_name": student.first_name,
                    "last_name": student.last_name,
                    "group": student.group.name,
                    "status": attempt_status(attempt),
                    "score": attempt.score if submitted else None,
                    "max_score": attempt.max_score if submitted else None,
                    "percent": percent(attempt) if submitted else None,
                    "started_at": attempt.started_at if attempt else None,
                    "submitted_at": attempt.submitted_at if attempt else None,
                }
            )
        return Response(rows)


class ExperimentView(APIView):
    """Tajriba natijasining statistik tahlili (kirish/chiqish/kechiktirilgan testlar): ruxsat etilgan barcha guruhlar."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from labs.statistics import allowed_groups

        from .experiment import analyse

        if request.user.is_student:
            raise PermissionDenied("Tahlil faqat admin va o'qituvchi uchun.")
        quizzes = Quiz.objects.all() if request.user.is_admin else Quiz.objects.filter(author=request.user)
        return Response(analyse(quizzes, allowed_groups(request.user)))


class ExpertPanelViewSet(viewsets.ModelViewSet):
    """Ekspert baholashlari: admin — barchasi, o'qituvchi — o'zi yaratganlari. Ekspertlar havola orqali baholaydi."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete"]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.user.is_student:
            raise PermissionDenied("Ekspert baholashi faqat admin va o'qituvchi uchun.")

    def get_queryset(self):
        from .expert import visible_panels

        queryset = visible_panels(self.request.user)
        quiz_id = self.request.query_params.get("quiz")
        if quiz_id:
            if not quiz_id.isdigit():
                raise ValidationError({"quiz": "Test raqami butun son bo'lishi kerak."})
            queryset = queryset.filter(quiz_id=quiz_id)
        return queryset

    def get_serializer_class(self):
        from .serializers import ExpertPanelSerializer

        return ExpertPanelSerializer

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "with_results": self.action != "list"}

    @action(detail=True, methods=["post"])
    def invites(self, request, pk=None):
        """{"label"} — yangi ekspert havolasi. Javobdagi token faqat shu safar ko'rsatiladi."""
        from .expert import create_invite

        panel = self.get_object()
        label = request.data.get("label")
        if not isinstance(label, str) or not label.strip() or len(label) > 200:
            raise ValidationError({"label": "Ekspert uchun belgi kiriting (200 belgigacha)."})
        if panel.invites.count() >= 50:
            raise ValidationError({"detail": "Bitta baholashga 50 tadan ortiq ekspert qo'shib bo'lmaydi."})
        invite, token = create_invite(panel, label.strip())
        return Response({"invite": invite_payload(invite), "token": token}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path=r"invites/(?P<invite_id>\d+)/(?P<operation>renew|revoke)")
    def invite_action(self, request, pk=None, invite_id=None, operation=None):
        """renew — yangi havola (eskisi ishlamaydi), revoke — havolani bekor qilish (baholar hisobdan chiqadi)."""
        from .expert import renew_token

        panel = self.get_object()
        invite = get_object_or_404(panel.invites, pk=invite_id)
        if operation == "revoke":
            invite.revoked = True
            invite.save(update_fields=["revoked", "updated_at"])
            return Response({"invite": invite_payload(invite)})
        if invite.submitted_at:
            raise ValidationError({"detail": "Ekspert baholarini yuborgan: havolani yangilash shart emas."})
        invite.revoked = False
        token = renew_token(invite)
        invite.save(update_fields=["revoked"])
        return Response({"invite": invite_payload(invite), "token": token})


def invite_payload(invite):
    return {
        "id": invite.pk,
        "label": invite.label,
        "revoked": invite.revoked,
        "started": bool(invite.ratings),
        "rated": len(invite.ratings),
        "submitted_at": invite.submitted_at,
        "created_at": invite.created_at,
    }


class ExpertRatingView(APIView):
    """Ekspert sahifasi (login talab qilinmaydi, shaxsiy havola tokeni bilan).

    GET — ko'rsatma va savollar (to'g'ri javoblar bilan: ekspert savol sifatini baholaydi), saqlangan baholar.
    PUT {"expert", "ratings", "submit"} — oraliq saqlash yoki yakuniy yuborish (keyin o'zgartirilmaydi).
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "expert"

    def invite(self, token):
        from .expert import find_invite

        invite = find_invite(token)
        if invite is None:
            raise NotFound("Havola noto'g'ri yoki bekor qilingan.")
        return invite

    def payload(self, invite):
        from .expert import SCALES

        panel = invite.panel
        return {
            "title": panel.title,
            "quiz_title": panel.quiz_title,
            "construct": panel.construct,
            "instructions": panel.instructions,
            "label": invite.label,
            "open": panel.is_open(),
            "closes_at": panel.closes_at,
            "submitted_at": invite.submitted_at,
            "items": panel.items,
            "scales": {name: {"min": low, "max": high} for name, (low, high) in SCALES.items()},
            "expert": invite.expert,
            "ratings": invite.ratings,
        }

    def get(self, request, token):
        return Response(self.payload(self.invite(token)))

    def put(self, request, token):
        from .expert import RatingsError, save_ratings

        invite = self.invite(token)
        if not invite.panel.is_open():
            raise ValidationError({"detail": "Baholash muddati tugagan."})
        submit = request.data.get("submit", False)
        if not isinstance(submit, bool):
            raise ValidationError({"submit": "Qiymat true yoki false bo'lishi kerak."})
        try:
            invite = save_ratings(invite, request.data.get("expert", {}), request.data.get("ratings", {}), submit)
        except RatingsError as exc:
            raise ValidationError({"detail": str(exc)})
        return Response(self.payload(invite))
