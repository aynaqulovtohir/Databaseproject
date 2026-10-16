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
            "stage",
            "sql_code",
            "diagram",
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
    # Bosqichli loyihada bosqich id'si (view tekshiradi: shu topshiriqqa tegishlimi)
    stage = serializers.IntegerField(required=False, allow_null=True, default=None)
    # ER-diagramma bosqichida
    diagram = serializers.JSONField(required=False, allow_null=True, default=None)
    sql_code = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=MAX_SQL_CODE_LENGTH,
        trim_whitespace=False,
        error_messages={
            "blank": "SQL kod bo'sh bo'lmasligi kerak.",
            "required": "SQL kod kiritilishi shart.",
            "max_length": "SQL kod {max_length} belgidan oshmasligi kerak.",
        },
    )

    def check_for(self, stage):
        """Bosqich turiga qarab yechimni tekshiradi. Qaytaradi: (sql_code, diagram)."""
        from labs.er import DiagramError, validate_diagram

        data = self.validated_data
        if stage is not None and stage.kind == stage.Kind.ER:
            if data["diagram"] is None:
                raise serializers.ValidationError({"diagram": "ER-diagrammani chizing."})
            try:
                diagram = validate_diagram(data["diagram"])
            except DiagramError as exc:
                raise serializers.ValidationError({"diagram": str(exc)})
            if not diagram["entities"]:
                raise serializers.ValidationError({"diagram": "Diagrammada kamida bitta obyekt bo'lsin."})
            return "", diagram
        if not data["sql_code"].strip():
            raise serializers.ValidationError({"sql_code": "SQL kod bo'sh bo'lmasligi kerak."})
        return data["sql_code"], None
