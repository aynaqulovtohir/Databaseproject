"""Foydalanuvchilar, guruhlar va shaxsiy kabinet API'lari."""
from datetime import UTC, datetime

from django.conf import settings
from django.db.models import ProtectedError
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from . import consent, tokens
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
        str(refresh_token),
        # Cookie token bilan bir vaqtda tugaydi (yangilanganda ham login vaqtidan hisoblanadi)
        expires=datetime.fromtimestamp(refresh_token["exp"], tz=UTC),
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite="Strict",
        path=settings.REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response):
    response.delete_cookie(
        settings.REFRESH_COOKIE_NAME, path=settings.REFRESH_COOKIE_PATH, samesite="Strict"
    )


class LoginSerializer(TokenObtainSerializer):
    def validate(self, attrs):
        # Parol va bloklanganlik tekshiruvi; muvaffaqiyatli bo'lsa self.user o'rnatiladi
        super().validate(attrs)
        # Berilgan token ro'yxatga olinadi: keyin uni bekor qilish mumkin bo'lsin
        self.refresh_token = tokens.issue(self.user)
        return {"access": str(self.refresh_token.access_token)}


class LoginView(TokenObtainPairView):
    """Login. Javobda faqat access token qaytadi; refresh token cookie'ga yoziladi.

    Parolni ketma-ket sinab topishdan himoya: urinishlar soni cheklangan.
    """

    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response = Response(serializer.validated_data)
        set_refresh_cookie(response, serializer.refresh_token)
        return response


class RefreshView(APIView):
    """Cookie'dagi refresh token orqali yangi access token beradi; refresh token har safar almashtiriladi."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if refresh_token:
            try:
                access, new_refresh = tokens.rotate(refresh_token)
            except tokens.RefreshFailed:
                pass
            else:
                response = Response({"access": access})
                if new_refresh is not None:
                    set_refresh_cookie(response, new_refresh)
                return response

        # Token yo'q, muddati o'tgan, bekor qilingan yoki foydalanuvchi bloklangan: qayta login kerak
        response = Response(
            {"detail": "Sessiya tugagan. Qayta kiring."}, status=status.HTTP_401_UNAUTHORIZED
        )
        clear_refresh_cookie(response)
        return response


class LogoutView(APIView):
    """Chiqish: refresh token bekor qilinadi va cookie o'chiriladi."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if refresh_token:
            tokens.revoke(refresh_token)
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
                    "detail": "Bu foydalanuvchining material, topshiriq yoki laboratoriyalari bor. "
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
        user = serializer.save()
        response = Response({"detail": "Parol o'zgartirildi."}, status=status.HTTP_200_OK)
        # Parol almashtirilganda barcha sessiyalar yopiladi (models.User.save); shu qurilma esa kirgan holda qoladi
        set_refresh_cookie(response, tokens.issue(user))
        return response


class ConsentView(APIView):
    """Tadqiqotga rozilik: GET — matn va joriy qaror, POST {"agreed": true|false} — talaba qarori."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "consent"

    def get(self, request):
        return Response(consent.status_payload(request.user))

    def post(self, request):
        if not request.user.is_student:
            raise ValidationError({"detail": "Rozilik faqat talabalardan so'raladi."})
        agreed = request.data.get("agreed")
        if not isinstance(agreed, bool):
            raise ValidationError({"agreed": "Qiymat true yoki false bo'lishi kerak."})
        consent.record_decision(request.user, agreed)
        return Response(consent.status_payload(request.user))
