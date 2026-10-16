from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from submissions.models import Submission
from users.models import StudentGroup, User

from .models import Assignment, AssignmentStage, Material, MaterialFile
from .rubric import MAX_STAGES, RubricError, clean_rubric, structure
from .validators import validate_material_file


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "first_name", "last_name"]


class MaterialFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialFile
        fields = ["id", "original_name", "size", "uploaded_at"]


class MaterialFileUploadSerializer(serializers.Serializer):
    file = serializers.FileField(validators=[validate_material_file])


class GroupsValidationMixin:
    """O'qituvchi faqat o'ziga biriktirilgan guruhlarni tanlay oladi."""

    def validate_groups(self, groups):
        if not groups:
            raise serializers.ValidationError("Kamida bitta guruh tanlang.")
        user = self.context["request"].user
        if user.is_teacher:
            own_group_ids = set(user.teaching_groups.values_list("id", flat=True))
            if any(group.id not in own_group_ids for group in groups):
                raise serializers.ValidationError(
                    "Faqat o'zingizga biriktirilgan guruhlarni tanlashingiz mumkin."
                )
        return groups


class MaterialSerializer(GroupsValidationMixin, serializers.ModelSerializer):
    """Admin va o'qituvchi uchun."""

    author = AuthorSerializer(read_only=True)
    groups = serializers.PrimaryKeyRelatedField(many=True, queryset=StudentGroup.objects.all())
    files = MaterialFileSerializer(many=True, read_only=True)

    class Meta:
        model = Material
        fields = ["id", "title", "text", "author", "groups", "files", "created_at"]
        read_only_fields = ["id", "created_at"]


class StudentMaterialSerializer(serializers.ModelSerializer):
    """Talaba uchun: boshqa guruhlar ro'yxati ko'rsatilmaydi."""

    author = AuthorSerializer(read_only=True)
    files = MaterialFileSerializer(many=True, read_only=True)

    class Meta:
        model = Material
        fields = ["id", "title", "text", "author", "files", "created_at"]
        read_only_fields = fields


class StageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssignmentStage
        fields = ["id", "order", "title", "description", "deadline"]
        read_only_fields = ["id", "order"]
        extra_kwargs = {"description": {"required": False, "allow_blank": True, "max_length": 5000}}


class AssignmentSerializer(GroupsValidationMixin, serializers.ModelSerializer):
    """Admin va o'qituvchi uchun.

    Bosqichlar ichma-ich saqlanadi (ro'yxat to'liq yuboriladi). Yechimlar kelgandan keyin bosqichlar soni,
    mezonlar ballari va bosqichga biriktirilishi o'zgartirilmaydi: qo'yilgan baholar ma'nosini yo'qotmasin.
    """

    author = AuthorSerializer(read_only=True)
    groups = serializers.PrimaryKeyRelatedField(many=True, queryset=StudentGroup.objects.all())
    stages = StageSerializer(many=True, required=False)
    rubric = serializers.JSONField(required=False)
    has_submissions = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            "id",
            "title",
            "description",
            "grading_criteria",
            "rubric",
            "stages",
            "author",
            "groups",
            "deadline",
            "has_submissions",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {"deadline": {"required": False}}

    def get_has_submissions(self, assignment):
        return assignment.submissions.exists()

    def check_future(self, deadline, previous):
        # Muddat o'zgartirilmagan bo'lsa (tahrirlashda), qayta tekshirilmaydi
        if previous != deadline and deadline <= timezone.now():
            raise serializers.ValidationError("Muddat kelajakdagi vaqt bo'lishi kerak.")

    def validate_deadline(self, deadline):
        self.check_future(deadline, self.instance.deadline if self.instance else None)
        return deadline

    def validate(self, attrs):
        current = self.instance
        locked = bool(current and current.submissions.exists())
        old_stages = list(current.stages.all()) if current else []
        stages = attrs.get("stages")
        stage_count = len(stages) if stages is not None else len(old_stages)
        if stage_count > MAX_STAGES:
            raise serializers.ValidationError({"stages": f"Bosqichlar {MAX_STAGES} tadan oshmasin."})

        if stages is not None:
            if locked and len(stages) != len(old_stages):
                raise serializers.ValidationError(
                    {"stages": "Yechimlar kelgan: bosqichlar sonini o'zgartirib bo'lmaydi."}
                )
            previous_deadline = None
            for order, stage in enumerate(stages):
                old = old_stages[order].deadline if order < len(old_stages) else None
                try:
                    self.check_future(stage["deadline"], old)
                except serializers.ValidationError:
                    raise serializers.ValidationError({"stages": f"{order + 1}-bosqich muddati kelajakda bo'lsin."})
                if previous_deadline and stage["deadline"] < previous_deadline:
                    raise serializers.ValidationError(
                        {"stages": f"{order + 1}-bosqich muddati oldingi bosqichnikidan keyin bo'lsin."}
                    )
                previous_deadline = stage["deadline"]
            if stages:
                # Loyiha muddati — oxirgi bosqich muddati
                attrs["deadline"] = stages[-1]["deadline"]
        if "deadline" not in attrs and current is None:
            raise serializers.ValidationError({"deadline": "Muddat kiritilishi shart."})

        rubric = attrs.get("rubric", current.rubric if current else [])
        try:
            cleaned = clean_rubric(rubric, stage_count)
        except RubricError as exc:
            raise serializers.ValidationError({"rubric": str(exc)})
        if locked and structure(cleaned) != structure(current.rubric):
            raise serializers.ValidationError(
                {"rubric": "Yechimlar kelgan: mezonlar ballari va bosqichlarini o'zgartirib bo'lmaydi "
                 "(nomi va izohini o'zgartirish mumkin)."}
            )
        attrs["rubric"] = cleaned
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        stages = validated_data.pop("stages", [])
        assignment = super().create(validated_data)
        AssignmentStage.objects.bulk_create(
            AssignmentStage(assignment=assignment, order=order, **stage) for order, stage in enumerate(stages)
        )
        return assignment

    @transaction.atomic
    def update(self, instance, validated_data):
        stages = validated_data.pop("stages", None)
        locked = instance.submissions.exists()
        assignment = super().update(instance, validated_data)
        if stages is not None:
            if locked:
                # Soni o'zgarmagan (validate); faqat matn va muddat yangilanadi
                for stage, data in zip(assignment.stages.all(), stages):
                    for field, value in data.items():
                        setattr(stage, field, value)
                    stage.save()
            else:
                assignment.stages.all().delete()
                AssignmentStage.objects.bulk_create(
                    AssignmentStage(assignment=assignment, order=order, **stage) for order, stage in enumerate(stages)
                )
        return assignment


class StudentAssignmentSerializer(serializers.ModelSerializer):
    """Talaba uchun: o'qituvchining yashirin baholash mezonlari (grading_criteria) va guruhlar ro'yxati
    ko'rsatilmaydi. Rubrika esa ko'rinadi: talaba nima uchun ball olishini oldindan bilsin."""

    author = AuthorSerializer(read_only=True)
    stages = StageSerializer(many=True, read_only=True)
    my_submission = serializers.SerializerMethodField()
    my_stages = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            "id",
            "title",
            "description",
            "rubric",
            "stages",
            "author",
            "deadline",
            "created_at",
            "my_submission",
            "my_stages",
        ]
        read_only_fields = fields

    def get_my_stages(self, assignment):
        """Har bir bosqich bo'yicha talabaning oxirgi urinishi va jami ball (faqat baholangan bosqichlar)."""
        stages = list(assignment.stages.all())
        if not stages:
            return None
        attempts = getattr(assignment, "my_attempts", None) or []
        latest = {}
        for attempt in attempts:  # yangisidan eskisiga
            latest.setdefault(attempt.stage_id, attempt)
        items, total, graded_any = [], 0, False
        for stage in stages:
            attempt = latest.get(stage.pk)
            grade = getattr(attempt, "grade", None) if attempt and attempt.status == Submission.Status.GRADED else None
            if grade:
                total += grade.score
                graded_any = True
            items.append(
                {
                    "stage": stage.pk,
                    "status": attempt.status if attempt else None,
                    "is_late": attempt.is_late if attempt else False,
                    "score": grade.score if grade else None,
                    "max_score": grade.max_score if grade else None,
                }
            )
        return {"items": items, "total_score": total if graded_any else None}

    def get_my_submission(self, assignment):
        # Talabaning shu topshiriqdagi oxirgi urinishi (view'da oldindan yuklab qo'yiladi)
        attempts = getattr(assignment, "my_attempts", None)
        if not attempts:
            return None
        latest = attempts[0]
        graded = latest.status == Submission.Status.GRADED
        grade = getattr(latest, "grade", None) if graded else None
        return {
            "id": latest.pk,
            "status": latest.status,
            "is_late": latest.is_late,
            "attempt_number": latest.attempt_number,
            "score": grade.score if grade else None,
        }
