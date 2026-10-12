"""AI tahlili va chat-yordamchi API'lari."""
import logging
from datetime import datetime, time

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from learning.access import visible_assignments
from submissions.access import visible_submissions

from .client import AIError, AINotConfigured, AITransientError
from .models import AIAnalysis, ChatMessage
from .serializers import (
    ChatMessageSerializer,
    ChatQuestionSerializer,
    StaffAnalysisSerializer,
    StudentAnalysisSerializer,
)
from .services import chat_reply

logger = logging.getLogger(__name__)

# AI'ga yuboriladigan oldingi xabarlar soni (juft bo'lishi kerak: savol + javob)
CHAT_HISTORY_LIMIT = 20


def get_visible_analysis(user, submission_pk):
    submission = get_object_or_404(visible_submissions(user), pk=submission_pk)
    return get_object_or_404(AIAnalysis, submission=submission)


class SubmissionAnalysisView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, submission_pk):
        analysis = get_visible_analysis(request.user, submission_pk)
        if request.user.is_student:
            serializer = StudentAnalysisSerializer(analysis)
        else:
            serializer = StaffAnalysisSerializer(analysis)
        return Response(serializer.data)


class SubmissionAnalysisRetryView(APIView):
    """Xato bilan tugagan tahlilni qayta navbatga qo'yish (o'qituvchi yoki admin)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, submission_pk):
        if request.user.is_student:
            raise PermissionDenied("Bu amal faqat admin yoki o'qituvchi uchun.")
        analysis = get_visible_analysis(request.user, submission_pk)
        updated = AIAnalysis.objects.filter(pk=analysis.pk, status=AIAnalysis.Status.FAILED).update(
            status=AIAnalysis.Status.PENDING, attempts=0, error_message="", completed_at=None
        )
        if not updated:
            raise ValidationError({"detail": "Faqat xato bilan tugagan tahlilni qayta ishga tushirish mumkin."})
        analysis.refresh_from_db()
        return Response(StaffAnalysisSerializer(analysis).data)


class AssignmentChatView(APIView):
    """Talabaning shu topshiriq bo'yicha AI bilan yozishmasi. Faqat talabaning o'zi ko'radi."""

    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user.is_student:
            raise PermissionDenied("Chat-yordamchi faqat talaba uchun.")
        self.assignment = get_object_or_404(visible_assignments(request.user), pk=kwargs["assignment_pk"])

    def own_messages(self):
        return ChatMessage.objects.filter(assignment=self.assignment, student=self.request.user)

    def messages_sent_today(self):
        day_start = timezone.make_aware(datetime.combine(timezone.localdate(), time.min))
        return ChatMessage.objects.filter(
            student=self.request.user, role=ChatMessage.Role.USER, created_at__gte=day_start
        ).count()

    def get(self, request, assignment_pk):
        return Response(
            {
                "messages": ChatMessageSerializer(self.own_messages(), many=True).data,
                "daily_limit": settings.AI_CHAT_DAILY_LIMIT,
                "used_today": self.messages_sent_today(),
            }
        )

    def post(self, request, assignment_pk):
        serializer = ChatQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data["content"]

        if self.messages_sent_today() >= settings.AI_CHAT_DAILY_LIMIT:
            return Response(
                {"detail": f"Bugungi xabarlar limiti ({settings.AI_CHAT_DAILY_LIMIT} ta) tugadi. Ertaga davom eting."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Oxirgi xabarlar, eski -> yangi tartibda
        recent = list(self.own_messages().order_by("-created_at", "-id")[:CHAT_HISTORY_LIMIT])[::-1]
        history = [{"role": message.role, "content": message.content} for message in recent]

        try:
            answer = chat_reply(self.assignment, history, question)
        except AINotConfigured:
            return Response(
                {"detail": "AI yordamchi hali sozlanmagan. Administratorga murojaat qiling."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except AITransientError:
            return Response(
                {"detail": "AI yordamchi vaqtincha ishlamayapti. Birozdan keyin qayta urinib ko'ring."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except AIError as exc:
            logger.error("Chat xatosi: %s", exc)
            return Response(
                {"detail": "AI bu xabarga javob bera olmadi. Savolni boshqacha yozib ko'ring."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Savol va javob faqat AI muvaffaqiyatli javob berganda saqlanadi,
        # shuning uchun xato bo'lgan urinish kunlik limitdan yechilmaydi
        with transaction.atomic():
            user_message = ChatMessage.objects.create(
                assignment=self.assignment, student=request.user, role=ChatMessage.Role.USER, content=question
            )
            assistant_message = ChatMessage.objects.create(
                assignment=self.assignment, student=request.user, role=ChatMessage.Role.ASSISTANT, content=answer
            )

        return Response(
            {
                "question": ChatMessageSerializer(user_message).data,
                "answer": ChatMessageSerializer(assistant_message).data,
                "used_today": self.messages_sent_today(),
                "daily_limit": settings.AI_CHAT_DAILY_LIMIT,
            },
            status=status.HTTP_201_CREATED,
        )
