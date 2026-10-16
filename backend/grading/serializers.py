from rest_framework import serializers

from users.models import User

from .models import MAX_SCORE, Grade

MAX_COMMENT_LENGTH = 5000


class GraderSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "first_name", "last_name"]


class StudentGradeSerializer(serializers.ModelSerializer):
    """Talaba uchun: AI taklif qilgan ball ko'rsatilmaydi."""

    class Meta:
        model = Grade
        fields = ["score", "max_score", "rubric_scores", "comment", "graded_at", "updated_at"]
        read_only_fields = fields


class StaffGradeSerializer(serializers.ModelSerializer):
    graded_by = GraderSerializer(read_only=True)

    class Meta:
        model = Grade
        fields = [
            "score",
            "max_score",
            "rubric_scores",
            "comment",
            "ai_suggested_score",
            "graded_by",
            "graded_at",
            "updated_at",
        ]
        read_only_fields = fields


class GradeInputSerializer(serializers.Serializer):
    """Rubrikasiz topshiriqda — score (0–100); rubrika bo'lsa — rubric_scores (har bir mezon uchun ball)."""

    rubric_scores = serializers.ListField(
        child=serializers.IntegerField(min_value=0, error_messages={"min_value": "Ball manfiy bo'lmasin."}),
        required=False,
        max_length=50,
    )
    score = serializers.IntegerField(
        required=False,
        min_value=0,
        max_value=MAX_SCORE,
        error_messages={
            "required": "Ball kiritilishi shart.",
            "invalid": "Ball butun son bo'lishi kerak.",
            "min_value": "Ball 0 dan kichik bo'lmasligi kerak.",
            "max_value": f"Ball {MAX_SCORE} dan oshmasligi kerak.",
        },
    )
    comment = serializers.CharField(
        required=False, allow_blank=True, max_length=MAX_COMMENT_LENGTH, default=""
    )


class ReturnInputSerializer(serializers.Serializer):
    comment = serializers.CharField(
        max_length=MAX_COMMENT_LENGTH,
        error_messages={
            "required": "Qaytarish sababini yozing.",
            "blank": "Qaytarish sababini yozing.",
        },
    )
