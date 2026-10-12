"""Foydalanuvchilar, guruhlar va shaxsiy kabinet API'lari."""
from django.conf import settings
from django.db.models import ProtectedError
from rest_framework import status, viewsets
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import StudentGroup, User
from .permissions import IsAdmin
from .serializers import (
    ChangePasswordSerializer,
    MeSerializer,
    StudentGroupSerializer,
    UserSerializer,
)


def set_refresh_cookie(response, refresh_token):
    """Refresh tokenni httpOnly cookie'ga yozadi: JavaScript uni o'qiy olmaydi."""
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite="Strict",
        path=settings.REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response):
    response.delete_cookie(
        settings.REFRESH_COOKIE_NAME, path=settings.REFRESH_COOKIE_PATH, samesite="Strict"
    )


class LoginView(TokenObtainPairView):
    """Login. Javobda faqat access token qaytadi; refresh token cookie'ga yoziladi.

    Parolni ketma-ket sinab topishdan himoya: urinishlar soni cheklangan.
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        refresh_token = response.data.pop("refresh", None)
        if refresh_token:
            set_refresh_cookie(response, refresh_token)
        return response


class RefreshView(APIView):
    """Cookie'dagi refresh token orqali yangi access token beradi."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if refresh_token:
            serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
            try:
                serializer.is_valid(raise_exception=True)
            except (TokenError, InvalidToken, AuthenticationFailed):
                pass
            else:
                return Response({"access": serializer.validated_data["access"]})

        # Token yo'q, muddati o'tgan yoki foydalanuvchi bloklangan: qayta login kerak
        response = Response(
            {"detail": "Sessiya tugagan. Qayta kiring."}, status=status.HTTP_401_UNAUTHORIZED
        )
        clear_refresh_cookie(response)
        return response


class LogoutView(APIView):
    """Chiqish: refresh cookie o'chiriladi."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response


class UserViewSet(viewsets.ModelViewSet):
    """Faqat admin: foydalanuvchilarni yaratish, tahrirlash, bloklash, o'chirish."""

    queryset = User.objects.select_related("group").prefetch_related("teaching_groups")
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]

    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            raise ValidationError({"detail": "O'zingizni o'chira olmaysiz."})
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError(
                {
                    "detail": "Bu foydalanuvchining material yoki topshiriqlari bor. "
                    "O'chirish o'rniga uni bloklang."
                }
            )


class StudentGroupViewSet(viewsets.ModelViewSet):
    """Faqat admin: guruhlarni boshqarish va o'qituvchilarni biriktirish."""

    queryset = StudentGroup.objects.prefetch_related("teachers", "students")
    serializer_class = StudentGroupSerializer
    permission_classes = [IsAdmin]


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Parol o'zgartirildi."}, status=status.HTTP_200_OK)
