from django.urls import path

from .views import AIUsageView, AssignmentChatView, SubmissionAnalysisRetryView, SubmissionAnalysisView

urlpatterns = [
    path("submissions/<int:submission_pk>/analysis/", SubmissionAnalysisView.as_view(), name="submission-analysis"),
    path(
        "submissions/<int:submission_pk>/analysis/retry/",
        SubmissionAnalysisRetryView.as_view(),
        name="submission-analysis-retry",
    ),
    path("assignments/<int:assignment_pk>/chat/", AssignmentChatView.as_view(), name="assignment-chat"),
    path("ai/usage/", AIUsageView.as_view(), name="ai-usage"),
]
