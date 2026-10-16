"""Virtual laboratoriya: talaba SQL kodni yozadi, tizim uni ishga tushirib tekshiradi."""
from django.conf import settings
from django.db import models

MAX_SQL_LENGTH = 50_000


class Lab(models.Model):
    class Kind(models.TextChoices):
        SQL = "sql", "SQL kod"
        ER = "er", "ER-diagramma"

    kind = models.CharField("turi", max_length=10, choices=Kind.choices, default=Kind.SQL)
    title = models.CharField("sarlavha", max_length=200)
    description = models.TextField("laboratoriya sharti")
    # Talabaga shart yonida ko'rinadi: qisqa nazariya va boshqa mavzudagi ishlangan namuna. Kod ``` bilan ajratiladi
    theory = models.TextField("nazariya va namuna", blank=True, max_length=20_000)
    # Har bir ishga tushirishdan oldin bajariladi: tayyor jadvallar va ma'lumotlar
    setup_sql = models.TextField("boshlang'ich jadvallar (SQL)", blank=True, max_length=MAX_SQL_LENGTH)
    # Talabaga ko'rinmaydi; talaba natijasi shu yechim natijasi bilan solishtiriladi
    solution_sql = models.TextField("namunaviy yechim (SQL)", blank=True, max_length=MAX_SQL_LENGTH)
    # ER-diagramma laboratoriyasi uchun namunaviy diagramma (labs/er.py dagi format); talabaga ko'rinmaydi
    reference_diagram = models.JSONField("namunaviy ER-diagramma", null=True, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="muallif",
        on_delete=models.PROTECT,
        related_name="labs",
    )
    groups = models.ManyToManyField("users.StudentGroup", verbose_name="guruhlar", related_name="labs")
    created_at = models.DateTimeField("yaratilgan vaqti", auto_now_add=True)

    class Meta:
        verbose_name = "laboratoriya"
        verbose_name_plural = "laboratoriyalar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class LabAttempt(models.Model):
    """Talabaning bitta ishga tushirishi."""

    lab = models.ForeignKey(Lab, verbose_name="laboratoriya", on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="talaba",
        on_delete=models.CASCADE,
        related_name="lab_attempts",
    )
    sql_code = models.TextField("SQL kod", max_length=MAX_SQL_LENGTH, blank=True)
    # ER-diagramma laboratoriyasida: talaba chizgan diagramma
    diagram = models.JSONField("ER-diagramma", null=True, blank=True)
    # Baholashga topshirilgan noto'g'ri diagramma uchun: tuzatilgan diagramma va AI tushuntirishi
    fixed_diagram = models.JSONField("tuzatilgan diagramma", null=True, blank=True)
    fix_explanation = models.TextField("tuzatish tushuntirishi", blank=True)
    is_correct = models.BooleanField("to'g'ri")
    # Baza xatosi va namunadan farqlar (AI maslahati uchun saqlanadi)
    feedback = models.JSONField("tekshiruv natijasi", default=dict)
    # Oxirgi (eng batafsil) olingan maslahat; bo'sh bo'lmasa — talaba AI maslahatidan foydalangan
    ai_advice = models.TextField("AI maslahati", blank=True)
    # Bosqichma-bosqich maslahatlar: 1 — yo'naltiruvchi savol, 2 — tushuncha, 3 — aniq ko'rsatma
    ai_hints = models.JSONField("AI maslahatlari (darajalar bo'yicha)", default=list, blank=True)
    ai_hint_level = models.PositiveSmallIntegerField("olingan maslahat darajasi", default=0)
    # AI maslahati so'ralgan vaqt (kunlik limitni hisoblash uchun)
    ai_requested_at = models.DateTimeField("AI maslahati so'ralgan vaqti", null=True, blank=True)
    # True - talaba bu urinishni baholashga topshirgan (oddiy ishga tushirish emas)
    is_submission = models.BooleanField("baholashga topshirilgan", default=False)
    # Urinish vaqtida talabaning guruhida AI yoqilganmi (tajriba tahlili uchun saqlanadi)
    ai_enabled = models.BooleanField("AI yoqilgan edi", default=True)
    created_at = models.DateTimeField("vaqti", auto_now_add=True)

    class Meta:
        verbose_name = "laboratoriya urinishi"
        verbose_name_plural = "laboratoriya urinishlari"
        ordering = ["-id"]
        indexes = [models.Index(fields=["lab", "student"])]

    def __str__(self):
        return f"{self.lab} / {self.student} / {"to'g'ri" if self.is_correct else "xato"}"


class LabGrade(models.Model):
    """Talabaning laboratoriya bo'yicha bahosi: topshirganlari ichidan eng yuqorisi saqlanadi."""

    class Source(models.TextChoices):
        AI = "ai", "Sun'iy intellekt"
        AUTO = "auto", "Avtomatik tekshiruv"

    lab = models.ForeignKey(Lab, verbose_name="laboratoriya", on_delete=models.CASCADE, related_name="grades")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="talaba",
        on_delete=models.CASCADE,
        related_name="lab_grades",
    )
    # Shu baho qo'yilgan urinish
    attempt = models.ForeignKey(LabAttempt, verbose_name="urinish", on_delete=models.CASCADE, related_name="+")
    score = models.PositiveSmallIntegerField("ball")
    comment = models.TextField("izoh", blank=True)
    source = models.CharField("kim baholagan", max_length=10, choices=Source.choices)
    graded_at = models.DateTimeField("baholangan vaqti", auto_now=True)

    class Meta:
        verbose_name = "laboratoriya bahosi"
        verbose_name_plural = "laboratoriya baholari"
        constraints = [models.UniqueConstraint(fields=["lab", "student"], name="unique_lab_grade_per_student")]

    def __str__(self):
        return f"{self.lab} / {self.student}: {self.score}"


class BlindReview(models.Model):
    """Ko'r baholash: o'qituvchi topshirilgan ishni AI bahosini va talaba ismini ko'rmasdan baholaydi.

    Keyin ikki baho o'rtasidagi moslik hisoblanadi (blind_review.py). Baho qo'yilgan paytdagi AI bahosi
    shu yerda saqlanadi: talaba keyin qayta topshirsa ham solishtiriladigan juftlik o'zgarmaydi.
    Baho bir marta qo'yiladi va o'zgartirilmaydi (keyin AI bahosini ko'rib "tuzatish" natijani buzadi).
    """

    attempt = models.ForeignKey(
        LabAttempt, verbose_name="urinish", on_delete=models.CASCADE, related_name="blind_reviews"
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="baholovchi", on_delete=models.CASCADE, related_name="blind_reviews"
    )
    score = models.PositiveSmallIntegerField("o'qituvchi bahosi")
    ai_score = models.PositiveSmallIntegerField("tizim bahosi")
    ai_source = models.CharField("tizim bahosi manbasi", max_length=10, choices=LabGrade.Source.choices)
    created_at = models.DateTimeField("baholangan vaqti", auto_now_add=True)

    class Meta:
        verbose_name = "ko'r baholash"
        verbose_name_plural = "ko'r baholashlar"
        ordering = ["id"]
        constraints = [models.UniqueConstraint(fields=["attempt", "reviewer"], name="unique_blind_review")]

    def __str__(self):
        return f"{self.attempt} / {self.reviewer}: {self.score} (tizim: {self.ai_score})"
