from rest_framework import serializers

from .models import AIAnalysis, ChatMessage

MAX_CHAT_MESSAGE_LENGTH = 4000


class StudentAnalysisSerializer(serializers.ModelSerializer):
    """Talaba uchun: taklif qilingan ball va uning asosi ko'rsatilmaydi."""

    class Meta:
        model = AIAnalysis
        fields = ["status", "summary", "issues", "recommendations", "completed_at"]
        read_only_fields = fields


class StaffAnalysisSerializer(serializers.ModelSerializer):
    """O'qituvchi va admin uchun: to'liq natija."""

    class Meta:
        model = AIAnalysis
        fields = [
            "status",
            "summary",
            "issues",
            "recommendations",
            "suggested_score",
            "score_rationale",
            "error_message",
            "model_name",
            "completed_at",
        ]
        read_only_fields = fields


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ["id", "role", "content", "created_at"]
        read_only_fields = fields


class ChatQuestionSerializer(serializers.Serializer):
    content = serializers.CharField(
        max_length=MAX_CHAT_MESSAGE_LENGTH,
        error_messages={
            "blank": "Xabar bo'sh bo'lmasligi kerak.",
            "required": "Xabar matni kiritilishi shart.",
            "max_length": "Xabar {max_length} belgidan oshmasligi kerak.",
        },
    )
