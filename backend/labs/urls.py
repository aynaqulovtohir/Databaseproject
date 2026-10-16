from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import LabAttemptAdviceView, LabChatView, LabViewSet, StatisticsView

router = SimpleRouter()
router.register("labs", LabViewSet, basename="lab")

# Urinish manzili router'dan oldin turishi shart ("attempts" id deb o'qilmasligi uchun)
urlpatterns = [
    path("labs/attempts/<int:pk>/advice/", LabAttemptAdviceView.as_view(), name="lab-attempt-advice"),
    path("labs/<int:pk>/chat/", LabChatView.as_view(), name="lab-chat"),
    path("statistics/", StatisticsView.as_view(), name="statistics"),
] + router.urls
