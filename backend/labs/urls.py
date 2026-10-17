from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    AIQualityView,
    LabAttemptAdviceView,
    LabAttemptExplainView,
    LabAnalysisView,
    LabChatView,
    LabModuleViewSet,
    LabStudyAdviceView,
    LabInterviewView,
    LabPeerReviewView,
    LabViewSet,
    PeerReviewHelpfulView,
    RiskView,
    StatisticsView,
)

router = SimpleRouter()
router.register("labs", LabViewSet, basename="lab")
router.register("lab-modules", LabModuleViewSet, basename="lab-module")

# Urinish manzili router'dan oldin turishi shart ("attempts" id deb o'qilmasligi uchun)
urlpatterns = [
    path("labs/attempts/<int:pk>/advice/", LabAttemptAdviceView.as_view(), name="lab-attempt-advice"),
    path("labs/attempts/<int:pk>/explain/", LabAttemptExplainView.as_view(), name="lab-attempt-explain"),
    path("labs/<int:pk>/chat/", LabChatView.as_view(), name="lab-chat"),
    path("labs/<int:pk>/study-advice/", LabStudyAdviceView.as_view(), name="lab-study-advice"),
    path("labs/<int:pk>/interview/", LabInterviewView.as_view(), name="lab-interview"),
    path("labs/<int:pk>/peer-review/", LabPeerReviewView.as_view(), name="lab-peer-review"),
    path("labs/peer-reviews/<int:pk>/helpful/", PeerReviewHelpfulView.as_view(), name="peer-review-helpful"),
    path("statistics/", StatisticsView.as_view(), name="statistics"),
    path("statistics/labs-analysis/", LabAnalysisView.as_view(), name="labs-analysis"),
    path("risk/", RiskView.as_view(), name="risk"),
    path("ai-quality/", AIQualityView.as_view(), name="ai-quality"),
] + router.urls
