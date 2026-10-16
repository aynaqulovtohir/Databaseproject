"""Baho qo'yish va qayta ishlashga qaytarish API'lari."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai.models import AIAnalysis
from learning.rubric import criteria_for
from notifications.services import notify_returned
from submissions.access import visible_submissions
from submissions.models import Submission
from submissions.serializers import SubmissionSerializer

from .models import MAX_SCORE, Grade
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
            .filter(
                assignment_id=submission.assignment_id,
                student_id=submission.student_id,
                stage_id=submission.stage_id,
            )
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
            score, max_score, rubric_scores = self.score_from(submission, serializer.validated_data)
            grade, created = Grade.objects.get_or_create(
                submission=submission,
                defaults={
                    "score": score,
                    "max_score": max_score,
                    "rubric_scores": rubric_scores,
                    "comment": serializer.validated_data["comment"],
                    "graded_by": request.user,
                    "ai_suggested_score": self.get_ai_suggested_score(submission, max_score),
                },
            )
            if not created:
                grade.score, grade.max_score, grade.rubric_scores = score, max_score, rubric_scores
                grade.comment = serializer.validated_data["comment"]
                grade.graded_by = request.user
                if grade.ai_suggested_score is None:
                    grade.ai_suggested_score = self.get_ai_suggested_score(submission, max_score)
                grade.save()

            submission.status = Submission.Status.GRADED
            submission.save(update_fields=["status"])

        return self.respond(submission)

    @staticmethod
    def score_from(submission, data):
        """Qaytaradi: (ball, eng yuqori ball, mezonlar bo'yicha ballar yoki None)."""
        criteria = criteria_for(submission.assignment, submission.stage)
        if not criteria:
            if data.get("score") is None:
                raise ValidationError({"score": "Ball kiritilishi shart."})
            return data["score"], MAX_SCORE, None
        scores = data.get("rubric_scores")
        if scores is None or len(scores) != len(criteria):
            raise ValidationError({"rubric_scores": f"Har bir mezon ({len(criteria)} ta) uchun ball qo'ying."})
        for item, value in zip(criteria, scores):
            if value > item["points"]:
                raise ValidationError({"rubric_scores": f"«{item['name']}» uchun ball {item['points']} dan oshmasin."})
        rubric_scores = [
            {"name": item["name"], "points": item["points"], "score": value} for item, value in zip(criteria, scores)
        ]
        return sum(scores), sum(item["points"] for item in criteria), rubric_scores

    @staticmethod
    def get_ai_suggested_score(submission, max_score=MAX_SCORE):
        """AI 0–100 shkalada baholaydi; bosqichda ball shu bosqichning eng yuqori baliga moslanadi."""
        analysis = AIAnalysis.objects.filter(submission=submission, status=AIAnalysis.Status.DONE).first()
        if not analysis or analysis.suggested_score is None:
            return None
        return round(analysis.suggested_score * max_score / MAX_SCORE)


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
