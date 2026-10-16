from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    LabAttemptAdviceView,
    LabAttemptExplainView,
    LabChatView,
    LabInterviewView,
    LabViewSet,
    StatisticsView,
)

router = SimpleRouter()
router.register("labs", LabViewSet, basename="lab")

# Urinish manzili router'dan oldin turishi shart ("attempts" id deb o'qilmasligi uchun)
urlpatterns = [
    path("labs/attempts/<int:pk>/advice/", LabAttemptAdviceView.as_view(), name="lab-attempt-advice"),
    path("labs/attempts/<int:pk>/explain/", LabAttemptExplainView.as_view(), name="lab-attempt-explain"),
    path("labs/<int:pk>/chat/", LabChatView.as_view(), name="lab-chat"),
    path("labs/<int:pk>/interview/", LabInterviewView.as_view(), name="lab-interview"),
    path("statistics/", StatisticsView.as_view(), name="statistics"),
] + router.urls
