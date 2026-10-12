"""Yechim topshirish va ko'rish API'lari."""
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from learning.access import visible_assignments

from .access import visible_submissions
from .models import Submission
from .serializers import SubmissionCreateSerializer, SubmissionSerializer


class AssignmentSubmissionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get_assignment(self):
        # Foydalanuvchi ko'ra olmaydigan topshiriq uchun 404 qaytadi
        return get_object_or_404(visible_assignments(self.request.user), pk=self.kwargs["assignment_pk"])

    def get(self, request, assignment_pk):
        assignment = self.get_assignment()
        submissions = visible_submissions(request.user).filter(assignment=assignment)

        if request.user.is_student:
            # Talaba: o'zining barcha urinishlari
            submissions = submissions.order_by("-attempt_number")
        else:
            student_id = request.query_params.get("student")
            if student_id is not None:
                if not student_id.isdigit():
                    raise ValidationError({"student": "Talaba id raqam bo'lishi kerak."})
                # Bitta talabaning barcha urinishlari
                submissions = submissions.filter(student_id=student_id).order_by("-attempt_number")
            else:
                # Har bir talabaning faqat oxirgi urinishi
                submissions = submissions.order_by("student_id", "-attempt_number").distinct("student_id")

        return Response(SubmissionSerializer(submissions, many=True, context={"request": request}).data)

    def post(self, request, assignment_pk):
        if not request.user.is_student:
            raise PermissionDenied("Yechimni faqat talaba topshira oladi.")
        assignment = self.get_assignment()

        serializer = SubmissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                last_submission = (
                    Submission.objects.select_for_update()
                    .filter(assignment=assignment, student=request.user)
                    .order_by("-attempt_number")
                    .first()
                )
                if last_submission and last_submission.status == Submission.Status.GRADED:
                    raise ValidationError(
                        {"detail": "Bu topshiriq baholangan. Qayta topshirish uchun o'qituvchi uni qaytarishi kerak."}
                    )
                submission = Submission.objects.create(
                    assignment=assignment,
                    student=request.user,
                    sql_code=serializer.validated_data["sql_code"],
                    attempt_number=(last_submission.attempt_number + 1) if last_submission else 1,
                    is_late=timezone.now() > assignment.deadline,
                )
        except IntegrityError:
            # Bir vaqtda ikki marta yuborilgan (masalan, tugma ikki marta bosilgan)
            return Response(
                {"detail": "Yechim allaqachon yuborilmoqda. Qayta urinib ko'ring."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            SubmissionSerializer(submission, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class SubmissionDetailView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SubmissionSerializer

    def get_queryset(self):
        return visible_submissions(self.request.user)
