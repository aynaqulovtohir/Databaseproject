"""Foydalanuvchi va guruh modellari."""
from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models


class UserManager(DjangoUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        # createsuperuser bilan yaratilgan foydalanuvchi har doim admin rolida bo'ladi
        extra_fields["role"] = User.Role.ADMIN
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        TEACHER = "teacher", "O'qituvchi"
        STUDENT = "student", "Talaba"

    role = models.CharField("rol", max_length=10, choices=Role.choices, default=Role.STUDENT)
    # Faqat talabalar uchun: talaba bitta guruhda bo'ladi
    group = models.ForeignKey(
        "StudentGroup",
        verbose_name="guruh",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="students",
    )

    # Ilmiy tadqiqotda ishtirok etishga rozilik (faqat talabalar): None — hali qaror bermagan.
    # Batafsil: users/consent.py; har bir qaror tarixi ResearchConsent jadvalida
    research_consent = models.BooleanField("tadqiqotga rozilik", null=True, blank=True)
    research_consent_version = models.CharField("rozilik matni versiyasi", max_length=10, blank=True)
    research_consent_at = models.DateTimeField("rozilik qarori vaqti", null=True, blank=True)

    objects = UserManager()

    class Meta:
        verbose_name = "foydalanuvchi"
        verbose_name_plural = "foydalanuvchilar"
        ordering = ["id"]

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def ai_allowed(self):
        """Talabaga AI yordamchisi (maslahat, AI bahosi, chat, tahlil) ko'rsatiladimi.

        Tajriba uchun nazorat guruhida AI o'chiriladi; xodimlar uchun har doim yoqilgan.
        """
        if not self.is_student:
            return True
        return bool(self.group and self.group.ai_enabled)


class StudentGroup(models.Model):
    name = models.CharField("nomi", max_length=100, unique=True)
    # Shu guruhga biriktirilgan o'qituvchilar
    teachers = models.ManyToManyField(
        User,
        verbose_name="o'qituvchilar",
        blank=True,
        related_name="teaching_groups",
        limit_choices_to={"role": User.Role.TEACHER},
    )
    # Tajriba: nazorat guruhida o'chiriladi, shunda AI ta'sirini alohida o'lchash mumkin
    ai_enabled = models.BooleanField("AI yordamchisi yoqilgan", default=True)
    created_at = models.DateTimeField("yaratilgan vaqti", auto_now_add=True)

    class Meta:
        verbose_name = "guruh"
        verbose_name_plural = "guruhlar"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ResearchConsent(models.Model):
    """Rozilik qarorlari tarixi: yozuvlar o'zgartirilmaydi va o'chirilmaydi (axloqiy nazorat uchun)."""

    user = models.ForeignKey(User, verbose_name="foydalanuvchi", on_delete=models.CASCADE, related_name="consent_history")
    agreed = models.BooleanField("rozi")
    version = models.CharField("rozilik matni versiyasi", max_length=10)
    created_at = models.DateTimeField("vaqti")

    class Meta:
        verbose_name = "tadqiqotga rozilik qarori"
        verbose_name_plural = "tadqiqotga rozilik qarorlari"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.user} / {'rozi' if self.agreed else 'rozi emas'} / {self.created_at:%Y-%m-%d}"
