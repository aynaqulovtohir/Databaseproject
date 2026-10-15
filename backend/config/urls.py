"""Loyihaning asosiy URL manzillari."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("users.urls")),
    path("api/", include("learning.urls")),
    path("api/", include("submissions.urls")),
    path("api/", include("ai.urls")),
    path("api/", include("grading.urls")),
    path("api/", include("notifications.urls")),
    path("api/", include("labs.urls")),
]
