"""Kompetentlik modeli va hisobotlari: faqat admin va o'qituvchi uchun (o'qituvchi — o'zi o'qitadigan guruhlar)."""
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from labs.statistics import allowed_groups

from .services import (
    LEVELS,
    OVERALL_HIGH_FROM,
    OVERALL_MEDIUM_FROM,
    STAGES,
    comparison,
    efficiency,
    group_report,
    load_model,
    model_payload,
)


class StaffView(APIView):
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.user.is_student:
            raise PermissionDenied("Kompetentlik hisobotlari faqat admin va o'qituvchi uchun.")


class CompetenceModelView(StaffView):
    def get(self, request):
        return Response(
            {
                "components": model_payload(load_model()),
                "stages": [{"key": key, "label": label} for key, label in STAGES.items()],
                "levels": [{"key": key, "label": label} for key, label in LEVELS.items()],
                "overall_thresholds": {"medium_from": OVERALL_MEDIUM_FROM, "high_from": OVERALL_HIGH_FROM},
            }
        )


class CompetenceReportView(StaffView):
    """?group=<id>&stage=initial|final — guruh talabalari bo'yicha batafsil."""

    def get(self, request):
        group_id = request.query_params.get("group", "")
        if not group_id.isdigit():
            raise ValidationError({"group": "Guruh raqami butun son bo'lishi kerak."})
        stage = request.query_params.get("stage", "final")
        if stage not in STAGES:
            raise ValidationError({"stage": f"Kesim quyidagilardan biri bo'lishi kerak: {', '.join(STAGES)}."})
        group = get_object_or_404(allowed_groups(request.user), pk=group_id)
        return Response(group_report(load_model(), group, stage))


class CompetenceComparisonView(StaffView):
    """Ruxsat etilgan barcha guruhlar: tajriba va nazorat guruhlari, ikkala kesimda."""

    def get(self, request):
        return Response(comparison(load_model(), list(allowed_groups(request.user))))


class CompetenceEfficiencyView(StaffView):
    """Statistik tahlil: tajriba va nazorat guruhlari solishtiruvi va o'sish (ruxsat etilgan guruhlar bo'yicha)."""

    def get(self, request):
        return Response(efficiency(load_model(), list(allowed_groups(request.user))))
