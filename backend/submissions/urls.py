from django.urls import path

from .views import AssignmentSubmissionsView, SubmissionDetailView

urlpatterns = [
    path(
        "assignments/<int:assignment_pk>/submissions/",
        AssignmentSubmissionsView.as_view(),
        name="assignment-submissions",
    ),
    path("submissions/<int:pk>/", SubmissionDetailView.as_view(), name="submission-detail"),
]
