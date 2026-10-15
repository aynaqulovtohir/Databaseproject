from django.db import transaction
from rest_framework import serializers

from learning.serializers import AuthorSerializer, GroupsValidationMixin
from users.models import StudentGroup

from .models import Choice, Question, Quiz
from .services import attempt_status, percent

MAX_QUESTIONS = 100
MIN_CHOICES = 2
MAX_CHOICES = 10


class ChoiceSerializer(serializers.ModelSerializer):
    text = serializers.CharField(max_length=1000)

    class Meta:
        model = Choice
        fields = ["id", "text", "is_correct"]
        read_only_fields = ["id"]


class QuestionSerializer(serializers.ModelSerializer):
    text = serializers.CharField(max_length=2000)
    points = serializers.IntegerField(min_value=1, max_value=100, default=1)
    choices = ChoiceSerializer(many=True)

    class Meta:
        model = Question
        fields = ["id", "text", "kind", "points", "choices"]
        read_only_fields = ["id"]

    def validate_choices(self, choices):
        if not MIN_CHOICES <= len(choices) <= MAX_CHOICES:
            raise serializers.ValidationError(f"Javob variantlari {MIN_CHOICES} tadan {MAX_CHOICES} tagacha bo'lsin.")
        return choices

    def validate(self, attrs):
        correct = sum(1 for choice in attrs["choices"] if choice.get("is_correct"))
        if attrs.get("kind", Question.Kind.SINGLE) == Question.Kind.SINGLE and correct != 1:
            raise serializers.ValidationError({"choices": "Bitta to'g'ri javobli savolda aynan bitta to'g'ri variant belgilang."})
        if correct < 1:
            raise serializers.ValidationError({"choices": "Kamida bitta to'g'ri variant belgilang."})
        return attrs


class QuizSerializer(GroupsValidationMixin, serializers.ModelSerializer):
    """Admin va o'qituvchi uchun: savollar to'g'ri javoblari bilan."""

    author = AuthorSerializer(read_only=True)
    groups = serializers.PrimaryKeyRelatedField(many=True, queryset=StudentGroup.objects.all())
    questions = QuestionSerializer(many=True, required=False)
    question_count = serializers.SerializerMethodField()
    attempt_count = serializers.SerializerMethodField()
    time_limit_minutes = serializers.IntegerField(min_value=1, max_value=600, required=False, allow_null=True)

    class Meta:
        model = Quiz
        fields = [
            "id",
            "kind",
            "title",
            "description",
            "opens_at",
            "closes_at",
            "time_limit_minutes",
            "show_answers",
            "groups",
            "author",
            "created_at",
            "questions",
            "question_count",
            "attempt_count",
        ]
        read_only_fields = ["id", "created_at"]

    def get_question_count(self, quiz):
        return len(quiz.questions.all())

    def get_attempt_count(self, quiz):
        return quiz.attempts.count()

    def validate_questions(self, questions):
        if not 1 <= len(questions) <= MAX_QUESTIONS:
            raise serializers.ValidationError(f"Testda 1 tadan {MAX_QUESTIONS} tagacha savol bo'lsin.")
        return questions

    def validate(self, attrs):
        current = self.instance
        if current is None and "questions" not in attrs:
            raise serializers.ValidationError({"questions": "Kamida bitta savol qo'shing."})
        if current is not None and "questions" in attrs and current.attempts.exists():
            raise serializers.ValidationError(
                {"questions": "Talabalar testni boshlagan: natijalar solishtirilishi uchun savollarni o'zgartirib bo'lmaydi."}
            )
        opens_at = attrs.get("opens_at", current.opens_at if current else None)
        closes_at = attrs.get("closes_at", current.closes_at if current else None)
        if opens_at and closes_at and closes_at <= opens_at:
            raise serializers.ValidationError({"closes_at": "Yopilish vaqti ochilish vaqtidan keyin bo'lsin."})
        return attrs

    @staticmethod
    def write_questions(quiz, questions):
        quiz.questions.all().delete()
        for order, data in enumerate(questions, start=1):
            choices = data.pop("choices")
            question = Question.objects.create(quiz=quiz, order=order, **data)
            Choice.objects.bulk_create(
                Choice(question=question, order=index, **choice) for index, choice in enumerate(choices, start=1)
            )

    @transaction.atomic
    def create(self, validated_data):
        questions = validated_data.pop("questions")
        quiz = super().create(validated_data)
        self.write_questions(quiz, questions)
        return quiz

    @transaction.atomic
    def update(self, instance, validated_data):
        questions = validated_data.pop("questions", None)
        quiz = super().update(instance, validated_data)
        if questions is not None:
            self.write_questions(quiz, questions)
        return quiz


class StudentQuizSerializer(serializers.ModelSerializer):
    """Talaba uchun: savollar va to'g'ri javoblarsiz, faqat o'z holati bilan."""

    author = AuthorSerializer(read_only=True)
    question_count = serializers.SerializerMethodField()
    is_open = serializers.SerializerMethodField()
    my_attempt = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = [
            "id",
            "kind",
            "title",
            "description",
            "opens_at",
            "closes_at",
            "time_limit_minutes",
            "author",
            "created_at",
            "question_count",
            "is_open",
            "my_attempt",
        ]
        read_only_fields = fields

    def get_question_count(self, quiz):
        return len(quiz.questions.all())

    def get_is_open(self, quiz):
        return quiz.is_open()

    def get_my_attempt(self, quiz):
        attempt = self.context.get("attempts", {}).get(quiz.pk)
        data = {"status": attempt_status(attempt)}
        if attempt and attempt.submitted_at:
            data.update(score=attempt.score, max_score=attempt.max_score, percent=percent(attempt),
                        submitted_at=attempt.submitted_at)
        elif attempt:
            data["deadline"] = attempt.deadline
        return data
