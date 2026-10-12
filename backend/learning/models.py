"""Material va topshiriq modellari."""
import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


def material_file_path(instance, filename):
    # Diskda tasodifiy nom bilan saqlanadi; asl nom alohida maydonda turadi
    extension = Path(filename).suffix.lower()
    return f"material_files/{uuid.uuid4().hex}{extension}"


class Material(models.Model):
    title = models.CharField("sarlavha", max_length=200)
    text = models.TextField("matn", blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="muallif",
        on_delete=models.PROTECT,
        related_name="materials",
    )
    groups = models.ManyToManyField(
        "users.StudentGroup", verbose_name="guruhlar", related_name="materials"
    )
    created_at = models.DateTimeField("yaratilgan vaqti", auto_now_add=True)

    class Meta:
        verbose_name = "material"
        verbose_name_plural = "materiallar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class MaterialFile(models.Model):
    material = models.ForeignKey(
        Material, verbose_name="material", on_delete=models.CASCADE, related_name="files"
    )
    file = models.FileField("fayl", upload_to=material_file_path)
    original_name = models.CharField("asl nomi", max_length=255)
    size = models.PositiveIntegerField("hajmi (bayt)")
    uploaded_at = models.DateTimeField("yuklangan vaqti", auto_now_add=True)

    class Meta:
        verbose_name = "material fayli"
        verbose_name_plural = "material fayllari"
        ordering = ["id"]

    def __str__(self):
        return self.original_name


@receiver(post_delete, sender=MaterialFile)
def delete_file_from_disk(sender, instance, **kwargs):
    # Yozuv o'chirilganda (material bilan birga ham) fayl diskdan ham o'chadi
    if instance.file:
        instance.file.delete(save=False)


class Assignment(models.Model):
    title = models.CharField("sarlavha", max_length=200)
    description = models.TextField("topshiriq sharti")
    # Talabaga ko'rinmaydi; AI tahlilida ishlatiladi
    grading_criteria = models.TextField("baholash mezonlari", blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="muallif",
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    groups = models.ManyToManyField(
        "users.StudentGroup", verbose_name="guruhlar", related_name="assignments"
    )
    deadline = models.DateTimeField("muddat")
    created_at = models.DateTimeField("yaratilgan vaqti", auto_now_add=True)

    class Meta:
        verbose_name = "topshiriq"
        verbose_name_plural = "topshiriqlar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
