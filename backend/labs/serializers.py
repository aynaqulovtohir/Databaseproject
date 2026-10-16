from rest_framework import serializers

from learning.serializers import AuthorSerializer, GroupsValidationMixin
from users.models import StudentGroup

from .checker import LabSetupError, format_error, validate_concurrent, validate_lab_sql, validate_plan
from .er import DiagramError, validate_diagram
from .interview import RequirementsError, validate_requirements
from .norm import NormError, parse_answer, parse_task, reference_solution
from .models import MAX_SQL_LENGTH, Lab
from .sandbox import SandboxUnavailable

SQL_TOO_LONG = "SQL kod {max_length} belgidan oshmasligi kerak."


def _task_input(value):
    """norm_task ni matn ({"attributes": "a, b", "fds": "a -> b", ...}) yoki saqlangan tuzilma ko'rinishida qabul qiladi."""
    if not isinstance(value, dict):
        raise NormError("Normallashtirish topshirig'i noto'g'ri formatda.")
    attributes = value.get("attributes", "")
    if isinstance(attributes, list):
        attributes = ", ".join(map(str, attributes))
    fds = value.get("fds", "")
    if isinstance(fds, list):
        fds = "\n".join(
            f"{', '.join(fd.get('lhs', []))} -> {', '.join(fd.get('rhs', []))}" for fd in fds if isinstance(fd, dict)
        )
    return parse_task(attributes, fds, value.get("target"))


class LabSerializer(GroupsValidationMixin, serializers.ModelSerializer):
    """Admin va o'qituvchi uchun."""

    author = AuthorSerializer(read_only=True)
    # Normallashtirish laboratoriyasi: o'qituvchiga ko'rinadigan hisoblangan javob (talabaga yuborilmaydi)
    norm_reference = serializers.SerializerMethodField()
    groups = serializers.PrimaryKeyRelatedField(many=True, queryset=StudentGroup.objects.all())
    setup_sql = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
        max_length=MAX_SQL_LENGTH,
        error_messages={"max_length": SQL_TOO_LONG},
    )
    solution_sql = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
        max_length=MAX_SQL_LENGTH,
        error_messages={"max_length": SQL_TOO_LONG},
    )
    starter_sql = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
        max_length=MAX_SQL_LENGTH,
        error_messages={"max_length": SQL_TOO_LONG},
    )
    hidden_setup_sql = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
        max_length=MAX_SQL_LENGTH,
        error_messages={"max_length": SQL_TOO_LONG},
    )

    class Meta:
        model = Lab
        fields = [
            "id",
            "kind",
            "title",
            "description",
            "theory",
            "setup_sql",
            "starter_sql",
            "solution_sql",
            "hidden_setup_sql",
            "reference_diagram",
            "given_diagram",
            "requirements",
            "client_persona",
            "norm_task",
            "norm_reference",
            "plan_query",
            "plan_forbidden",
            "concurrent",
            "topic",
            "effective_topic",
            "author",
            "groups",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "effective_topic"]

    def get_norm_reference(self, lab):
        return reference_solution(lab.norm_task) if lab.kind == Lab.Kind.NORM and lab.norm_task else None

    def validate(self, attrs):
        current = self.instance
        kind = attrs.get("kind", current.kind if current else Lab.Kind.SQL)
        if current and kind != current.kind:
            raise serializers.ValidationError({"kind": "Laboratoriya turini o'zgartirib bo'lmaydi."})
        if kind == Lab.Kind.ER:
            return self.validate_er(attrs)
        if kind == Lab.Kind.NORM:
            return self.validate_norm(attrs)
        attrs["norm_task"] = None
        attrs["reference_diagram"] = None
        attrs["requirements"], attrs["client_persona"] = [], ""
        given = attrs.get("given_diagram")
        if given is not None:
            try:
                given = validate_diagram(given)
            except DiagramError as exc:
                raise serializers.ValidationError({"given_diagram": str(exc)})
            # Bo'sh diagramma — berilmagan bilan teng
            attrs["given_diagram"] = given if given["entities"] else None
        return self.validate_sql(attrs)

    def validate_er(self, attrs):
        current = self.instance
        diagram = attrs.get("reference_diagram", current.reference_diagram if current else None)
        if diagram is None:
            raise serializers.ValidationError({"reference_diagram": "Namunaviy ER-diagrammani chizing."})
        try:
            diagram = validate_diagram(diagram)
        except DiagramError as exc:
            raise serializers.ValidationError({"reference_diagram": str(exc)})
        if not diagram["entities"]:
            raise serializers.ValidationError({"reference_diagram": "Namunaviy diagrammada kamida bitta obyekt bo'lsin."})
        attrs["reference_diagram"] = diagram
        if "requirements" in attrs:
            try:
                attrs["requirements"] = validate_requirements(attrs["requirements"])
            except RequirementsError as exc:
                raise serializers.ValidationError({"requirements": str(exc)})
        # ER laboratoriyasida SQL ishlatilmaydi
        attrs["setup_sql"] = attrs["solution_sql"] = attrs["hidden_setup_sql"] = attrs["plan_query"] = ""
        attrs["starter_sql"] = ""
        attrs["given_diagram"] = None
        attrs["concurrent"] = False
        return attrs

    def validate_norm(self, attrs):
        current = self.instance
        task = attrs.get("norm_task", current.norm_task if current else None)
        if task is None:
            raise serializers.ValidationError({"norm_task": "Atributlar va funksional bog'liqliklarni kiriting."})
        try:
            attrs["norm_task"] = _task_input(task)
        except NormError as exc:
            raise serializers.ValidationError({"norm_task": str(exc)})
        # Normallashtirishda SQL va diagramma ishlatilmaydi
        attrs["setup_sql"] = attrs["solution_sql"] = attrs["hidden_setup_sql"] = attrs["plan_query"] = ""
        attrs["starter_sql"] = ""
        attrs["reference_diagram"] = attrs["given_diagram"] = None
        attrs["requirements"], attrs["client_persona"] = [], ""
        attrs["concurrent"] = False
        return attrs

    def validate_sql(self, attrs):
        # SQL o'zgargan bo'lsa, u haqiqatan ishlashi tekshiriladi: xato laboratoriya talabaga yetib bormasin
        current = self.instance
        setup_sql = attrs.get("setup_sql", current.setup_sql if current else "")
        solution_sql = attrs.get("solution_sql", current.solution_sql if current else "")
        hidden_sql = attrs.get("hidden_setup_sql", current.hidden_setup_sql if current else "")
        plan_query = attrs.get("plan_query", current.plan_query if current else "")
        plan_forbidden = attrs.get("plan_forbidden", current.plan_forbidden if current else "Seq Scan")
        concurrent = attrs.get("concurrent", current.concurrent if current else False)
        values = (setup_sql, solution_sql, hidden_sql, plan_query, plan_forbidden, concurrent)
        changed = current is None or values != (
            current.setup_sql,
            current.solution_sql,
            current.hidden_setup_sql,
            current.plan_query,
            current.plan_forbidden,
            current.concurrent,
        )
        if concurrent and (plan_query.strip() or hidden_sql.strip()):
            raise serializers.ValidationError(
                {"concurrent": "Ikki sessiyali tekshiruv reja va yashirin ma'lumotlar bilan birga ishlatilmaydi."}
            )
        if concurrent and not solution_sql.strip():
            raise serializers.ValidationError({"solution_sql": "Tranzaksiya laboratoriyasida namunaviy yechim kerak."})
        if plan_query.strip() and not solution_sql.strip():
            raise serializers.ValidationError({"solution_sql": "Reja tekshiriladigan laboratoriyada namunaviy yechim (indeks) kerak."})
        if changed and (setup_sql.strip() or solution_sql.strip() or hidden_sql.strip()):
            try:
                validate_lab_sql(setup_sql, solution_sql, hidden_sql)
                if concurrent:
                    validate_concurrent(setup_sql, solution_sql)
                if plan_query.strip():
                    validate_plan(
                        setup_sql, solution_sql, plan_query, [item.strip() for item in plan_forbidden.split(",") if item.strip()]
                    )
            except LabSetupError as exc:
                raise serializers.ValidationError({exc.field: f"Kod xato berdi. {format_error(exc.error)}"})
            except SandboxUnavailable:
                raise serializers.ValidationError(
                    {"detail": "Laboratoriya bazasi vaqtincha ishlamayapti. Birozdan keyin qayta urinib ko'ring."}
                )
        return attrs


def grade_payload(grade):
    return {
        "score": grade.score,
        "comment": grade.comment,
        "source": grade.source,
        "graded_at": grade.graded_at,
    }


class StudentLabSerializer(serializers.ModelSerializer):
    """Talaba uchun: namunaviy yechim va guruhlar ro'yxati ko'rsatilmaydi."""

    author = AuthorSerializer(read_only=True)
    my_progress = serializers.SerializerMethodField()
    interview = serializers.SerializerMethodField()

    class Meta:
        model = Lab
        fields = [
            "id",
            "kind",
            "title",
            "description",
            "theory",
            "setup_sql",
            "starter_sql",
            "given_diagram",
            "norm_task",
            "plan_query",
            "concurrent",
            "effective_topic",
            "author",
            "created_at",
            "my_progress",
            "interview",
        ]
        read_only_fields = fields

    def get_interview(self, lab):
        """Talablarni aniqlash laboratoriyasi: AI yoqilgan guruhga talablar ko'rsatilmaydi (ularni buyurtmachidan
        so'rab aniqlaydi), nazorat guruhiga esa an'anaviy shart sifatida to'liq beriladi."""
        if not lab.is_interview:
            return None
        request = self.context.get("request")
        ai = bool(request and request.user.ai_allowed)
        return {"total": len(lab.requirements), "ai": ai, "requirements": None if ai else lab.requirements}

    def get_my_progress(self, lab):
        # Talabaning o'z urinishlari view'da oldindan yuklab qo'yiladi (yangisidan eskisiga)
        attempts = getattr(lab, "my_attempts", [])
        progress = {
            "attempts": len(attempts),
            "solved": any(attempt.is_correct for attempt in attempts),
        }
        grades = getattr(lab, "my_grades", [])
        progress["grade"] = grade_payload(grades[0]) if grades else None
        if self.context.get("include_last_code"):
            # Talaba sahifani qayta ochganda oxirgi yozgan kodi tiklanadi
            progress["last_code"] = attempts[0].sql_code if attempts else ""
            if lab.kind == Lab.Kind.NORM:
                progress["last_answer"] = attempts[0].answer if attempts else None
            if lab.kind == Lab.Kind.ER:
                progress["last_diagram"] = attempts[0].diagram if attempts else None
                # Oxirgi topshirilgan noto'g'ri diagrammaning tuzatilgan varianti
                submitted = next((attempt for attempt in attempts if attempt.is_submission), None)
                progress["last_fix"] = fix_payload(submitted) if submitted else None
        return progress


def fix_payload(attempt):
    if not attempt.fixed_diagram:
        return None
    return {"diagram": attempt.fixed_diagram, "explanation": attempt.fix_explanation}


class DiagramRunSerializer(serializers.Serializer):
    diagram = serializers.JSONField(error_messages={"required": "Diagramma yuborilmadi."})

    def validate_diagram(self, value):
        try:
            return validate_diagram(value)
        except DiagramError as exc:
            raise serializers.ValidationError(str(exc))


class NormAnswerSerializer(serializers.Serializer):
    answer = serializers.JSONField(error_messages={"required": "Javob yuborilmadi."})

    def __init__(self, *args, task=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.task = task

    def validate_answer(self, value):
        try:
            return parse_answer(value, self.task)
        except NormError as exc:
            raise serializers.ValidationError(str(exc))


class RunSerializer(serializers.Serializer):
    sql_code = serializers.CharField(
        max_length=MAX_SQL_LENGTH,
        trim_whitespace=False,
        error_messages={
            "blank": "SQL kod bo'sh bo'lmasligi kerak.",
            "required": "SQL kod kiritilishi shart.",
            "max_length": SQL_TOO_LONG,
        },
    )

    def validate_sql_code(self, value):
        if not value.strip():
            raise serializers.ValidationError("SQL kod bo'sh bo'lmasligi kerak.")
        return value
