from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    AssignmentViewSet,
    MaterialFileDetailView,
    MaterialFileDownloadView,
    MaterialViewSet,
)

router = SimpleRouter()
router.register("materials", MaterialViewSet, basename="material")
router.register("assignments", AssignmentViewSet, basename="assignment")

# Fayl manzillari router'dan oldin turishi shart ("files" id deb o'qilmasligi uchun)
urlpatterns = [
    path("materials/files/<int:pk>/", MaterialFileDetailView.as_view(), name="material-file-detail"),
    path(
        "materials/files/<int:pk>/download/",
        MaterialFileDownloadView.as_view(),
        name="material-file-download",
    ),
] + router.urls
