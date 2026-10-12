from django.utils import timezone
from rest_framework import serializers

from users.models import StudentGroup, User

from .models import Assignment, Material, MaterialFile
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


class AssignmentSerializer(GroupsValidationMixin, serializers.ModelSerializer):
    """Admin va o'qituvchi uchun."""

    author = AuthorSerializer(read_only=True)
    groups = serializers.PrimaryKeyRelatedField(many=True, queryset=StudentGroup.objects.all())

    class Meta:
        model = Assignment
        fields = [
            "id",
            "title",
            "description",
            "grading_criteria",
            "author",
            "groups",
            "deadline",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_deadline(self, deadline):
        # Muddat o'zgartirilmagan bo'lsa (tahrirlashda), qayta tekshirilmaydi
        if self.instance is not None and self.instance.deadline == deadline:
            return deadline
        if deadline <= timezone.now():
            raise serializers.ValidationError("Muddat kelajakdagi vaqt bo'lishi kerak.")
        return deadline


class StudentAssignmentSerializer(serializers.ModelSerializer):
    """Talaba uchun: baholash mezonlari va guruhlar ro'yxati ko'rsatilmaydi."""

    author = AuthorSerializer(read_only=True)

    class Meta:
        model = Assignment
        fields = ["id", "title", "description", "author", "deadline", "created_at"]
        read_only_fields = fields
