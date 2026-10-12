"""Telegram bog'lanishini boshqarish. Har bir foydalanuvchi faqat o'z bog'lanishini ko'radi."""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import linking, telegram
from .models import TelegramAccount


class TelegramStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        account = TelegramAccount.objects.filter(user=request.user).first()
        return Response(
            {
                "configured": telegram.is_configured(),
                "linked": account is not None,
                "linked_at": account.linked_at if account else None,
            }
        )

    def delete(self, request):
        linking.unlink_user(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TelegramLinkView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not telegram.is_configured():
            return Response(
                {"detail": "Telegram bot hali sozlanmagan. Administratorga murojaat qiling."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        url, expires_at = linking.create_link(request.user)
        return Response({"url": url, "expires_at": expires_at}, status=status.HTTP_201_CREATED)
