from django.urls import path

from .views import SubmissionGradeView, SubmissionReturnView

urlpatterns = [
    path("submissions/<int:submission_pk>/grade/", SubmissionGradeView.as_view(), name="submission-grade"),
    path("submissions/<int:submission_pk>/return/", SubmissionReturnView.as_view(), name="submission-return"),
]
