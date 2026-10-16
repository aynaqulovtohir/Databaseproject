"""Talabalarning ma'lumotlar bazasini loyihalash kompetentligi modeli: komponentlar, ko'rsatkichlar va darajalar.

Model bazada saqlanadi va admin panelda tahrirlanadi: komponentlar, ularning ko'rsatkichlari va daraja
chegaralari ilmiy rahbar bilan kelishilgan metodikaga moslanadi. Ko'rsatkich qiymatlari platformadagi
mavjud ma'lumotlardan hisoblanadi (testlar, so'rovnomalar, laboratoriyalar, baholar) — qo'shimcha ma'lumot
yig'ilmaydi. Hisob services.py da.
"""
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from labs.models import Lab


class Component(models.Model):
    """Kompetentlik komponenti (masalan, kognitiv yoki faoliyatli) va uning daraja chegaralari (foizda)."""

    name = models.CharField("nomi", max_length=100)
    description = models.TextField("tavsifi", blank=True, max_length=2000)
    order = models.PositiveSmallIntegerField("tartib raqami", default=0)
    # Ball [0, medium_from) — past, [medium_from, high_from) — o'rta, [high_from, 100] — yuqori daraja
    medium_from = models.PositiveSmallIntegerField(
        "o'rta daraja chegarasi (%)", default=40, validators=[MinValueValidator(1), MaxValueValidator(99)]
    )
    high_from = models.PositiveSmallIntegerField(
        "yuqori daraja chegarasi (%)", default=70, validators=[MinValueValidator(2), MaxValueValidator(100)]
    )

    class Meta:
        verbose_name = "komponent"
        verbose_name_plural = "komponentlar"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.medium_from is not None and self.high_from is not None and self.medium_from >= self.high_from:
            raise ValidationError({"high_from": "Yuqori daraja chegarasi o'rta daraja chegarasidan katta bo'lishi kerak."})


class Indicator(models.Model):
    """Komponent ko'rsatkichi: qiymati (0-100) qaysi ma'lumotdan va qaysi kesimda hisoblanishi."""

    class Source(models.TextChoices):
        QUIZ = "quiz", "Test natijasi"
        SURVEY = "survey", "So'rovnoma (Likert)"
        LABS = "labs", "Laboratoriyalar: yechilgan ulushi"
        MASTERY = "mastery", "Laboratoriyalar: o'zlashtirish (BKT)"
        EXPLANATION = "explanation", "Yechimni o'z so'zlari bilan tushuntirish"
        GRADES = "grades", "O'qituvchi baholari (topshiriqlar)"
        INTERVIEW = "interview", "Talablarni aniqlash (buyurtmachi bilan suhbat)"
        CALIBRATION = "calibration", "O'z bilimini baholash aniqligi (ishonch va natija)"
        PEER_ACCURACY = "peer_accuracy", "Hamkasb ishini baholash aniqligi (o'zaro baholash)"
        PEER_HELPFUL = "peer_helpful", "Izohlar foydaliligi (o'zaro baholash)"

    # Test va so'rovnoma har bir kesimda o'lchanadi (har biriga o'z testi), qolganlari — o'quv jarayoni
    # ma'lumotlari, ular faqat tajriba oxirida bor
    QUIZ_SOURCES = (Source.QUIZ, Source.SURVEY)
    TOPIC_SOURCES = (
        Source.LABS,
        Source.MASTERY,
        Source.EXPLANATION,
        Source.INTERVIEW,
        Source.CALIBRATION,
        Source.PEER_ACCURACY,
        Source.PEER_HELPFUL,
    )
    PEER_SOURCES = (Source.PEER_ACCURACY, Source.PEER_HELPFUL)
    # AI bilan bog'liq: nazorat guruhida (AI o'chirilgan) bu ko'rsatkichlar o'lchanmaydi
    AI_SOURCES = (Source.EXPLANATION, Source.INTERVIEW)

    component = models.ForeignKey(
        Component, verbose_name="komponent", on_delete=models.CASCADE, related_name="indicators"
    )
    name = models.CharField("nomi", max_length=200)
    source = models.CharField("ma'lumot manbasi", max_length=20, choices=Source.choices)
    weight = models.PositiveSmallIntegerField(
        "vazni", default=1, validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Komponent bali ko'rsatkichlarning vaznli o'rtachasi.",
    )
    order = models.PositiveSmallIntegerField("tartib raqami", default=0)
    # Bir kesimda bir nechta test bo'lishi mumkin (masalan, tajriba va nazorat guruhlari uchun alohida so'rovnoma):
    # talabaning qiymati o'zi topshirgan testdan olinadi
    initial_quizzes = models.ManyToManyField(
        "quizzes.Quiz", verbose_name="tajriba boshidagi testlar", blank=True, related_name="+",
        help_text="Faqat test va so'rovnoma manbalari uchun. Bo'sh bo'lsa, bu kesimda o'lchanmaydi.",
    )
    final_quizzes = models.ManyToManyField(
        "quizzes.Quiz", verbose_name="tajriba oxiridagi testlar", blank=True, related_name="+",
        help_text="Faqat test va so'rovnoma manbalari uchun. Bo'sh bo'lsa, bu kesimda o'lchanmaydi.",
    )
    # Kurs tugagandan bir necha hafta keyin (kechiktirilgan test): bilim qanchalik saqlanganini o'lchaydi
    delayed_quizzes = models.ManyToManyField(
        "quizzes.Quiz", verbose_name="tajribadan keyingi (kechiktirilgan) testlar", blank=True, related_name="+",
        help_text="Faqat test va so'rovnoma manbalari uchun. Bo'sh bo'lsa, bu kesimda o'lchanmaydi.",
    )
    # Laboratoriya manbalari uchun: qaysi mavzular hisobga olinadi (bo'sh — hammasi)
    topics = models.JSONField(
        "laboratoriya mavzulari", default=list, blank=True,
        help_text="Laboratoriya manbalari uchun mavzu kodlari ro'yxati, masalan [\"er\", \"norm\"]. Bo'sh — hammasi.",
    )

    class Meta:
        verbose_name = "ko'rsatkich"
        verbose_name_plural = "ko'rsatkichlar"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.component} / {self.name}"

    def clean(self):
        topics = self.topics or []
        valid = {choice for choice, _ in Lab.Topic.choices}
        if not isinstance(topics, list) or any(topic not in valid for topic in topics):
            raise ValidationError({"topics": f"Mavzu kodlari ro'yxati bo'lishi kerak, mumkin bo'lganlari: {', '.join(sorted(valid))}."})
        if topics and self.source not in self.TOPIC_SOURCES:
            raise ValidationError({"topics": "Mavzular faqat laboratoriya manbalari uchun beriladi."})
