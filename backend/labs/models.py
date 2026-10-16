"""Virtual laboratoriya: talaba SQL kodni yozadi, tizim uni ishga tushirib tekshiradi."""
from django.conf import settings
from django.db import models

MAX_SQL_LENGTH = 50_000


class Lab(models.Model):
    class Topic(models.TextChoices):
        # Kurs tartibida: moslashuvchan o'quv yo'li avval oldingi mavzuni o'zlashtirishni tavsiya qiladi
        ER = "er", "ER-model"
        DESIGN = "design", "Jadvallarni loyihalash"
        NORM = "norm", "Normallashtirish"
        ER_SQL = "er_sql", "ER-modeldan jadvallarga"
        SELECT = "select", "SELECT so'rovlari"
        INDEX = "index", "Indekslar"
        TRANSACTION = "transaction", "Tranzaksiyalar"
        VECTOR = "vector", "Vektorli qidiruv (AI)"

    class Kind(models.TextChoices):
        SQL = "sql", "SQL kod"
        ER = "er", "ER-diagramma"
        NORM = "norm", "Normallashtirish"

    kind = models.CharField("turi", max_length=10, choices=Kind.choices, default=Kind.SQL)
    title = models.CharField("sarlavha", max_length=200)
    description = models.TextField("laboratoriya sharti")
    # Talabaga shart yonida ko'rinadi: qisqa nazariya va boshqa mavzudagi ishlangan namuna. Kod ``` bilan ajratiladi
    theory = models.TextField("nazariya va namuna", blank=True, max_length=20_000)
    # Har bir ishga tushirishdan oldin bajariladi: tayyor jadvallar va ma'lumotlar
    setup_sql = models.TextField("boshlang'ich jadvallar (SQL)", blank=True, max_length=MAX_SQL_LENGTH)
    # Talaba muharririda dastlab turadigan kod (masalan, "AI yozgan xatoli yechim — xatoni toping" mashqi)
    starter_sql = models.TextField("boshlang'ich kod (talabaga)", blank=True, max_length=MAX_SQL_LENGTH)
    # Talabaga ko'rinmaydi; talaba natijasi shu yechim natijasi bilan solishtiriladi
    solution_sql = models.TextField("namunaviy yechim (SQL)", blank=True, max_length=MAX_SQL_LENGTH)
    # Talabaga ko'rinmaydi. To'g'ri chiqqan kod shu ma'lumotlarda ham namunaviy yechim bilan solishtiriladi:
    # natijani qo'lda yozib (SELECT 'Ali', 5) tekshiruvni aldab bo'lmaydi. Jadvallar setup_sql dagidek, ma'lumot boshqa
    hidden_setup_sql = models.TextField("yashirin test ma'lumotlari (SQL)", blank=True, max_length=MAX_SQL_LENGTH)
    # ER-diagramma laboratoriyasi uchun namunaviy diagramma (labs/er.py dagi format); talabaga ko'rinmaydi
    reference_diagram = models.JSONField("namunaviy ER-diagramma", null=True, blank=True)
    # Normallashtirish laboratoriyasi (labs/norm.py): {"attributes", "fds": [{"lhs", "rhs"}], "target"}. Talabaga ko'rinadi
    norm_task = models.JSONField("normallashtirish topshirig'i", null=True, blank=True)
    # SQL laboratoriyasida talabaga beriladigan ER-model (ER → SQL): talaba shu model bo'yicha jadvallarni yaratadi.
    # Talabaga ko'rinadi; tekshiruv o'zgarmaydi — jadvallar namunaviy yechim bilan solishtiriladi
    given_diagram = models.JSONField("berilgan ER-model", null=True, blank=True)
    # Indeks laboratoriyasi: talaba kodidan keyin shu so'rovning rejasi (EXPLAIN) olinadi va unda taqiqlangan
    # tugunlar (masalan, Seq Scan) bo'lmasligi kerak. So'rovning o'zi bajarilmaydi. Talabaga ko'rinadi
    plan_query = models.TextField("rejasi tekshiriladigan so'rov", blank=True, max_length=5000)
    # Vergul bilan: rejada bo'lmasligi kerak bo'lgan tugunlar
    plan_forbidden = models.CharField("rejada taqiqlangan tugunlar", max_length=200, blank=True, default="Seq Scan")
    # Tranzaksiya laboratoriyasi: talaba kodi (BEGIN ... COMMIT) ikki sessiyada bir vaqtda bajariladi va natija
    # ketma-ket bajarilgandagiga teng bo'lishi kerak (yo'qolgan yangilanish, "tekshir-keyin-bajar" poygasi)
    concurrent = models.BooleanField("ikki sessiyada bir vaqtda tekshiriladi", default=False)
    # Bo'sh bo'lsa, laboratoriya turidan aniqlanadi (effective_topic)
    topic = models.CharField("mavzu", max_length=20, choices=Topic.choices, blank=True)
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

    @property
    def effective_topic(self):
        """O'qituvchi bergan mavzu yoki laboratoriya turidan aniqlangani."""
        if self.topic:
            return self.topic
        if self.kind == self.Kind.ER:
            return self.Topic.ER
        if self.kind == self.Kind.NORM:
            return self.Topic.NORM
        if self.concurrent:
            return self.Topic.TRANSACTION
        if self.plan_query.strip():
            return self.Topic.INDEX
        if self.given_diagram:
            return self.Topic.ER_SQL
        if "create table" in self.solution_sql.lower():
            return self.Topic.DESIGN
        return self.Topic.SELECT


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
    # Normallashtirish laboratoriyasida: talaba javobi (kalitlar, normal forma, dekompozitsiya). Uning o'qiladigan
    # ko'rinishi sql_code ga ham yoziladi: o'qituvchi sahifasi, o'xshashlik va eksport uni matn sifatida ko'rsatadi
    answer = models.JSONField("javob", null=True, blank=True)
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
    # To'g'ri yechimdan keyin talaba o'z so'zlari bilan tushuntiradi (self-explanation); AI mosligini baholaydi.
    # Bahoga ta'sir qilmaydi: o'qituvchi tasodifan yoki ko'chirib topilgan javoblarni ko'rishi uchun
    self_explanation = models.TextField("talabaning tushuntirishi", blank=True, max_length=3000)
    explanation_verdict = models.CharField(
        "tushuntirish bahosi",
        max_length=10,
        blank=True,
        choices=[("ok", "Mos"), ("partial", "Qisman"), ("wrong", "Mos emas")],
    )
    explanation_feedback = models.TextField("tushuntirish bo'yicha izoh", blank=True)
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


class AIAction(models.Model):
    """Talabaning AI'dan foydalanishi (maslahatdan tashqari): kunlik umumiy limitni hisoblash uchun.

    Matn saqlanmaydi — faqat kim, qaysi turdagi so'rov va qachon.
    """

    class Kind(models.TextChoices):
        PLAN_EXPLAIN = "plan_explain", "EXPLAIN tushuntirishi"
        PLAN_SUGGEST = "plan_suggest", "Indeks taklifi"
        LAB_CHAT = "lab_chat", "Laboratoriya murabbiyi"
        SELF_EXPLAIN = "self_explain", "Yechimni tushuntirish"
        VIVA = "viva", "Loyiha himoyasi"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="talaba", on_delete=models.CASCADE, related_name="ai_actions"
    )
    kind = models.CharField("turi", max_length=20, choices=Kind.choices)
    created_at = models.DateTimeField("vaqti", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "AI so'rovi (talaba)"
        verbose_name_plural = "AI so'rovlari (talabalar)"
        ordering = ["-id"]


class LabChatMessage(models.Model):
    """Talabaning laboratoriya murabbiyi (AI) bilan yozishmasi. Faqat talabaning o'zi ko'radi."""

    class Role(models.TextChoices):
        USER = "user", "Talaba"
        ASSISTANT = "assistant", "AI"

    lab = models.ForeignKey(Lab, verbose_name="laboratoriya", on_delete=models.CASCADE, related_name="chat_messages")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="talaba", on_delete=models.CASCADE, related_name="lab_chat_messages"
    )
    role = models.CharField("kim yozgan", max_length=10, choices=Role.choices)
    content = models.TextField("matn")
    created_at = models.DateTimeField("vaqti", auto_now_add=True)

    class Meta:
        verbose_name = "murabbiy xabari"
        verbose_name_plural = "murabbiy xabarlari"
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["lab", "student"])]
