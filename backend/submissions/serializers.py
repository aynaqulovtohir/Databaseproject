from rest_framework import serializers

from grading.serializers import StaffGradeSerializer, StudentGradeSerializer
from users.models import User

from .models import MAX_SQL_CODE_LENGTH, Submission


class StudentShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "first_name", "last_name"]


class MissingStudentSerializer(serializers.ModelSerializer):
    """Yechim topshirmagan talaba: o'qituvchi kimga eslatishni bilishi uchun."""

    group = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "group"]


class SubmissionSerializer(serializers.ModelSerializer):
    student = StudentShortSerializer(read_only=True)
    grade = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            "id",
            "assignment",
            "student",
            "sql_code",
            "attempt_number",
            "is_late",
            "status",
            "grade",
            "return_comment",
            "submitted_at",
        ]
        read_only_fields = fields

    def get_grade(self, submission):
        grade = getattr(submission, "grade", None)
        if grade is None:
            return None
        request = self.context.get("request")
        # Faqat admin va o'qituvchi AI taklif qilgan ballni ko'radi
        if request and (request.user.is_admin or request.user.is_teacher):
            return StaffGradeSerializer(grade).data
        return StudentGradeSerializer(grade).data


class SubmissionCreateSerializer(serializers.Serializer):
    sql_code = serializers.CharField(
        max_length=MAX_SQL_CODE_LENGTH,
        trim_whitespace=False,
        error_messages={
            "blank": "SQL kod bo'sh bo'lmasligi kerak.",
            "required": "SQL kod kiritilishi shart.",
            "max_length": "SQL kod {max_length} belgidan oshmasligi kerak.",
        },
    )

    def validate_sql_code(self, value):
        if not value.strip():
            raise serializers.ValidationError("SQL kod bo'sh bo'lmasligi kerak.")
        return value
