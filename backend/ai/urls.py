from django.urls import path

from .views import (
    AIUsageView,
    AssignmentChatView,
    SubmissionAnalysisRetryView,
    SubmissionAnalysisView,
    SubmissionVivaView,
)

urlpatterns = [
    path("submissions/<int:submission_pk>/analysis/", SubmissionAnalysisView.as_view(), name="submission-analysis"),
    path(
        "submissions/<int:submission_pk>/analysis/retry/",
        SubmissionAnalysisRetryView.as_view(),
        name="submission-analysis-retry",
    ),
    path("submissions/<int:submission_pk>/viva/", SubmissionVivaView.as_view(), name="submission-viva"),
    path(
        "submissions/<int:submission_pk>/viva/answers/",
        SubmissionVivaView.as_view(),
        {"step": "answers"},
        name="submission-viva-answers",
    ),
    path("assignments/<int:assignment_pk>/chat/", AssignmentChatView.as_view(), name="assignment-chat"),
    path("ai/usage/", AIUsageView.as_view(), name="ai-usage"),
]
