from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import ExpertPanelViewSet, ExpertRatingView, ExperimentView, QuizViewSet

router = SimpleRouter()
router.register("quizzes", QuizViewSet, basename="quiz")
router.register("expert-panels", ExpertPanelViewSet, basename="expert-panel")

urlpatterns = [
    path("experiment/", ExperimentView.as_view(), name="experiment"),
    # Ekspert sahifasi: login yo'q, shaxsiy havola tokeni bilan
    path("expert/<str:token>/", ExpertRatingView.as_view(), name="expert-rating"),
] + router.urls
