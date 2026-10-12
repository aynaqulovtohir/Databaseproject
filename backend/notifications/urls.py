from django.urls import path

from .views import TelegramLinkView, TelegramStatusView

urlpatterns = [
    path("telegram/", TelegramStatusView.as_view(), name="telegram-status"),
    path("telegram/link/", TelegramLinkView.as_view(), name="telegram-link"),
]
