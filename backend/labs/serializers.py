from rest_framework import serializers

from learning.serializers import AuthorSerializer, GroupsValidationMixin
from users.models import StudentGroup

from .checker import LabSetupError, format_error, validate_lab_sql
from .er import DiagramError, validate_diagram
from .models import MAX_SQL_LENGTH, Lab
from .sandbox import SandboxUnavailable

SQL_TOO_LONG = "SQL kod {max_length} belgidan oshmasligi kerak."


class LabSerializer(GroupsValidationMixin, serializers.ModelSerializer):
    """Admin va o'qituvchi uchun."""

    author = AuthorSerializer(read_only=True)
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

    class Meta:
        model = Lab
        fields = [
            "id",
            "kind",
            "title",
            "description",
            "theory",
            "setup_sql",
            "solution_sql",
            "reference_diagram",
            "author",
            "groups",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        current = self.instance
        kind = attrs.get("kind", current.kind if current else Lab.Kind.SQL)
        if current and kind != current.kind:
            raise serializers.ValidationError({"kind": "Laboratoriya turini o'zgartirib bo'lmaydi."})
        if kind == Lab.Kind.ER:
            return self.validate_er(attrs)
        attrs["reference_diagram"] = None
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
        # ER laboratoriyasida SQL ishlatilmaydi
        attrs["setup_sql"] = attrs["solution_sql"] = ""
        return attrs

    def validate_sql(self, attrs):
        # SQL o'zgargan bo'lsa, u haqiqatan ishlashi tekshiriladi: xato laboratoriya talabaga yetib bormasin
        current = self.instance
        setup_sql = attrs.get("setup_sql", current.setup_sql if current else "")
        solution_sql = attrs.get("solution_sql", current.solution_sql if current else "")
        changed = current is None or (setup_sql, solution_sql) != (current.setup_sql, current.solution_sql)
        if changed and (setup_sql.strip() or solution_sql.strip()):
            try:
                validate_lab_sql(setup_sql, solution_sql)
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

    class Meta:
        model = Lab
        fields = ["id", "kind", "title", "description", "theory", "setup_sql", "author", "created_at", "my_progress"]
        read_only_fields = fields

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
