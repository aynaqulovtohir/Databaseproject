"""Ma'lumotni tekshirish va JSON ko'rinishiga o'tkazish."""
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import StudentGroup, User


def check_password_strength(password, user=None):
    """Django parol qoidalarini tekshiradi va xatoni DRF formatida qaytaradi."""
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages))


class StudentGroupSerializer(serializers.ModelSerializer):
    teachers = serializers.PrimaryKeyRelatedField(
        many=True,
        required=False,
        queryset=User.objects.filter(role=User.Role.TEACHER),
    )
    student_count = serializers.IntegerField(source="students.count", read_only=True)

    class Meta:
        model = StudentGroup
        fields = ["id", "name", "teachers", "student_count", "created_at"]
        read_only_fields = ["id", "created_at"]


class UserSerializer(serializers.ModelSerializer):
    """Admin foydalanuvchilarni boshqarishi uchun."""

    password = serializers.CharField(write_only=True, required=False, style={"input_type": "password"})
    teaching_groups = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "password",
            "first_name",
            "last_name",
            "role",
            "group",
            "teaching_groups",
            "is_active",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        instance = self.instance
        request_user = self.context["request"].user

        # Yangi foydalanuvchi yaratishda parol majburiy
        if instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "Parol kiritilishi shart."})

        if attrs.get("password"):
            candidate = instance or User(
                username=attrs.get("username", ""),
                first_name=attrs.get("first_name", ""),
                last_name=attrs.get("last_name", ""),
            )
            try:
                check_password_strength(attrs["password"], user=candidate)
            except serializers.ValidationError as exc:
                raise serializers.ValidationError({"password": exc.detail})

        # API orqali admin roli berilmaydi: adminlar faqat serverda
        # createsuperuser buyrug'i bilan yaratiladi
        if attrs.get("role") == User.Role.ADMIN and not (instance and instance.is_admin):
            raise serializers.ValidationError(
                {"role": "Admin rolini berib bo'lmaydi. Faqat o'qituvchi yoki talaba rolini tanlang."}
            )

        # Guruh faqat talabaga biriktiriladi
        role = attrs.get("role", instance.role if instance else User.Role.STUDENT)
        group = attrs.get("group", instance.group if instance else None)
        if group is not None and role != User.Role.STUDENT:
            if "group" in attrs:
                raise serializers.ValidationError({"group": "Guruh faqat talabaga biriktiriladi."})
            # Rol o'zgarganda eski guruh avtomatik olib tashlanadi
            attrs["group"] = None

        # Admin o'zini bloklab yoki rolini o'zgartirib, tizimdan uzilib qolmasin
        if instance is not None and instance.pk == request_user.pk:
            if attrs.get("is_active") is False:
                raise serializers.ValidationError({"is_active": "O'zingizni bloklay olmaysiz."})
            if "role" in attrs and attrs["role"] != User.Role.ADMIN:
                raise serializers.ValidationError({"role": "O'z rolingizni o'zgartira olmaysiz."})

        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        old_role = instance.role
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        # O'qituvchi boshqa rolga o'tsa, guruhlarga biriktiruvi olib tashlanadi
        if old_role == User.Role.TEACHER and instance.role != User.Role.TEACHER:
            instance.teaching_groups.clear()
        return instance


class GroupShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentGroup
        fields = ["id", "name"]


class MeSerializer(serializers.ModelSerializer):
    """Kirgan foydalanuvchining o'z ma'lumotlari."""

    group = GroupShortSerializer(read_only=True)
    teaching_groups = GroupShortSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "role", "group", "teaching_groups"]
        read_only_fields = fields


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Eski parol noto'g'ri.")
        return value

    def validate_new_password(self, value):
        check_password_strength(value, user=self.context["request"].user)
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user
