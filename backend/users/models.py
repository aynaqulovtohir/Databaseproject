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
    created_at = models.DateTimeField("yaratilgan vaqti", auto_now_add=True)

    class Meta:
        verbose_name = "guruh"
        verbose_name_plural = "guruhlar"
        ordering = ["name"]

    def __str__(self):
        return self.name
