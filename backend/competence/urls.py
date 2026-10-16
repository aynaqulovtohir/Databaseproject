from django.urls import path

from .views import CompetenceComparisonView, CompetenceEfficiencyView, CompetenceModelView, CompetenceReportView

urlpatterns = [
    path("competence/model/", CompetenceModelView.as_view(), name="competence-model"),
    path("competence/report/", CompetenceReportView.as_view(), name="competence-report"),
    path("competence/comparison/", CompetenceComparisonView.as_view(), name="competence-comparison"),
    path("competence/efficiency/", CompetenceEfficiencyView.as_view(), name="competence-efficiency"),
]
