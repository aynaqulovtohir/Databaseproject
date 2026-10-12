"""Baho qo'yish va qayta ishlashga qaytarish API'lari."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai.models import AIAnalysis
from notifications.services import notify_returned
from submissions.access import visible_submissions
from submissions.models import Submission
from submissions.serializers import SubmissionSerializer

from .models import Grade
from .serializers import GradeInputSerializer, ReturnInputSerializer


class ReviewBaseView(APIView):
    """Baholash va qaytarish uchun umumiy tekshiruvlar."""

    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not (request.user.is_admin or request.user.is_teacher):
            raise PermissionDenied("Bu amal faqat admin yoki o'qituvchi uchun.")

    def get_locked_latest_submission(self, submission_pk):
        """Yechimni qulflab oladi va u talabaning oxirgi urinishi ekanini tekshiradi.

        Tranzaksiya ichida chaqiriladi. Talabaning shu topshiriqdagi barcha urinishlari
        qulflanadi, shuning uchun baholash paytida yangi urinish qo'shilib qolmaydi.
        """
        # O'qituvchi faqat o'z topshirig'iga kelgan yechimni ko'ra oladi (aks holda 404)
        submission = get_object_or_404(visible_submissions(self.request.user), pk=submission_pk)
        attempts = list(
            Submission.objects.select_for_update()
            .filter(assignment_id=submission.assignment_id, student_id=submission.student_id)
            .order_by("-attempt_number")
        )
        if attempts[0].pk != submission.pk:
            raise ValidationError(
                {"detail": "Faqat talabaning oxirgi urinishini baholash yoki qaytarish mumkin."}
            )
        return attempts[0]

    def respond(self, submission):
        fresh = visible_submissions(self.request.user).get(pk=submission.pk)
        return Response(SubmissionSerializer(fresh, context={"request": self.request}).data)


class SubmissionGradeView(ReviewBaseView):
    def put(self, request, submission_pk):
        serializer = GradeInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            submission = self.get_locked_latest_submission(submission_pk)
            grade, created = Grade.objects.get_or_create(
                submission=submission,
                defaults={
                    "score": serializer.validated_data["score"],
                    "comment": serializer.validated_data["comment"],
                    "graded_by": request.user,
                    "ai_suggested_score": self.get_ai_suggested_score(submission),
                },
            )
            if not created:
                grade.score = serializer.validated_data["score"]
                grade.comment = serializer.validated_data["comment"]
                grade.graded_by = request.user
                if grade.ai_suggested_score is None:
                    grade.ai_suggested_score = self.get_ai_suggested_score(submission)
                grade.save()

            submission.status = Submission.Status.GRADED
            submission.save(update_fields=["status"])

        return self.respond(submission)

    @staticmethod
    def get_ai_suggested_score(submission):
        analysis = AIAnalysis.objects.filter(submission=submission, status=AIAnalysis.Status.DONE).first()
        return analysis.suggested_score if analysis else None


class SubmissionReturnView(ReviewBaseView):
    def post(self, request, submission_pk):
        serializer = ReturnInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            submission = self.get_locked_latest_submission(submission_pk)
            if submission.status == Submission.Status.RETURNED:
                raise ValidationError({"detail": "Bu yechim allaqachon qayta ishlashga qaytarilgan."})
            submission.status = Submission.Status.RETURNED
            submission.return_comment = serializer.validated_data["comment"]
            submission.save(update_fields=["status", "return_comment"])
            notify_returned(submission)

        return self.respond(submission)
