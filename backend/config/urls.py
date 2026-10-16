"""Loyihaning asosiy URL manzillari."""
from django.contrib import admin
from django.urls import include, path

from .health import HealthView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/", include("users.urls")),
    path("api/", include("learning.urls")),
    path("api/", include("submissions.urls")),
    path("api/", include("ai.urls")),
    path("api/", include("grading.urls")),
    path("api/", include("notifications.urls")),
    path("api/", include("labs.urls")),
    path("api/", include("quizzes.urls")),
    path("api/", include("competence.urls")),
]
