from django.db import transaction
from rest_framework import serializers

from learning.serializers import AuthorSerializer, GroupsValidationMixin
from users.models import StudentGroup

from .models import LIKERT_SCALE, Choice, ExpertPanel, Question, Quiz
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
    # Likert savolida variantlar yuborilmaydi: ular standart shkaladan olinadi
    choices = ChoiceSerializer(many=True, required=False)

    class Meta:
        model = Question
        fields = ["id", "text", "kind", "points", "choices"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        if attrs.get("kind") == Question.Kind.LIKERT:
            # Ball qo'yilmaydi; foydalanuvchi yuborgan variantlar hisobga olinmaydi
            attrs["points"] = 0
            attrs["choices"] = [{"text": text, "is_correct": False} for text in LIKERT_SCALE]
            return attrs
        choices = attrs.get("choices", [])
        if not MIN_CHOICES <= len(choices) <= MAX_CHOICES:
            raise serializers.ValidationError(
                {"choices": f"Javob variantlari {MIN_CHOICES} tadan {MAX_CHOICES} tagacha bo'lsin."}
            )
        correct = sum(1 for choice in attrs["choices"] if choice.get("is_correct"))
        if attrs.get("kind", Question.Kind.SINGLE) == Question.Kind.SINGLE and correct != 1:
            raise serializers.ValidationError({"choices": "Bitta to'g'ri javobli savolda aynan bitta to'g'ri variant belgilang."})
        if correct < 1:
            raise serializers.ValidationError({"choices": "Kamida bitta to'g'ri variant belgilang."})
        return attrs


RESEARCH_KINDS = (Quiz.Kind.PRE, Quiz.Kind.POST, Quiz.Kind.DELAYED)


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
            "form",
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
        kind = attrs.get("kind", current.kind if current else Quiz.Kind.PRACTICE)
        if "questions" in attrs:
            kinds = {question.get("kind", Question.Kind.SINGLE) for question in attrs["questions"]}
        elif current is not None:
            kinds = set(current.questions.values_list("kind", flat=True))
        else:
            kinds = set()
        # So'rovnomada faqat Likert savollari, testda esa faqat ball qo'yiladigan savollar bo'ladi
        if kind == Quiz.Kind.SURVEY and kinds - {Question.Kind.LIKERT}:
            raise serializers.ValidationError({"questions": "So'rovnomada faqat Likert shkalali savollar bo'ladi."})
        if kind != Quiz.Kind.SURVEY and Question.Kind.LIKERT in kinds:
            raise serializers.ValidationError({"questions": "Likert shkalali savollar faqat so'rovnomada bo'ladi."})
        if opens_at and closes_at and closes_at <= opens_at:
            raise serializers.ValidationError({"closes_at": "Yopilish vaqti ochilish vaqtidan keyin bo'lsin."})
        form = attrs.get("form", current.form if current else "")
        if form and kind not in RESEARCH_KINDS:
            raise serializers.ValidationError({"form": "Parallel variant faqat kirish, chiqish va kechiktirilgan testga beriladi."})
        if current is not None and "form" in attrs and attrs["form"] != current.form and current.attempts.exists():
            raise serializers.ValidationError({"form": "Talabalar testni boshlagan: variantni o'zgartirib bo'lmaydi."})
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


class ExpertPanelSerializer(serializers.ModelSerializer):
    """Ekspert baholashi. Yaratishda test tanlanadi va savollar nusxasi olinadi; keyin test o'zgarmaydi."""

    author = AuthorSerializer(read_only=True)
    quiz = serializers.PrimaryKeyRelatedField(queryset=Quiz.objects.all())
    items_count = serializers.SerializerMethodField()
    invites = serializers.SerializerMethodField()
    results = serializers.SerializerMethodField()

    class Meta:
        model = ExpertPanel
        fields = [
            "id", "quiz", "quiz_title", "title", "construct", "instructions", "closes_at",
            "author", "created_at", "items_count", "invites", "results",
        ]
        read_only_fields = ["id", "quiz_title", "author", "created_at"]
        extra_kwargs = {"construct": {"max_length": 2000}, "instructions": {"max_length": 3000}}

    def validate_quiz(self, quiz):
        from .views import visible_quizzes

        if not visible_quizzes(self.context["request"].user).filter(pk=quiz.pk).exists():
            raise serializers.ValidationError("Faqat o'zingizning testingizni tanlashingiz mumkin.")
        if not quiz.questions.exists():
            raise serializers.ValidationError("Testda hali savol yo'q.")
        return quiz

    def get_items_count(self, panel):
        return len(panel.items)

    def get_invites(self, panel):
        from .views import invite_payload

        return [invite_payload(invite) for invite in panel.invites.all()]

    def get_results(self, panel):
        from .expert import results

        return results(panel) if self.context.get("with_results") else None

    def create(self, validated_data):
        from .expert import snapshot

        quiz = validated_data["quiz"]
        return ExpertPanel.objects.create(
            **validated_data, quiz_title=quiz.title, items=snapshot(quiz), author=self.context["request"].user
        )

    def update(self, instance, validated_data):
        # Test va savollar nusxasi yaratilgandan keyin o'zgarmaydi (tuzatilgan versiya — yangi baholash)
        validated_data.pop("quiz", None)
        return super().update(instance, validated_data)
