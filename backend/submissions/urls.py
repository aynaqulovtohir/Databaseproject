from django.urls import path

from .views import AssignmentMissingStudentsView, AssignmentSubmissionsView, SubmissionDetailView

urlpatterns = [
    path(
        "assignments/<int:assignment_pk>/submissions/",
        AssignmentSubmissionsView.as_view(),
        name="assignment-submissions",
    ),
    path(
        "assignments/<int:assignment_pk>/missing-students/",
        AssignmentMissingStudentsView.as_view(),
        name="assignment-missing-students",
    ),
    path("submissions/<int:pk>/", SubmissionDetailView.as_view(), name="submission-detail"),
]
