"""Loyiha sozlamalari. Barcha maxfiy qiymatlar .env dan o'qiladi."""
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
)

# Docker'da qiymatlar muhit o'zgaruvchilari orqali keladi;
# Docker'siz ishga tushirilsa, loyiha ildizidagi .env o'qiladi.
env_file = BASE_DIR.parent / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

# Bu qiymatlar bo'lmasa, loyiha ishga tushmaydi (xato beradi)
SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "users",
    "learning",
    "submissions",
    "ai",
    "grading",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST"),
        "PORT": env("POSTGRES_PORT"),
    }
}

# O'zimizning foydalanuvchi modelimiz (rol va guruh bilan)
AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

# Yuklangan fayllar. Ochiq URL orqali berilmaydi, faqat API orqali yuklab olinadi.
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# API'ga faqat JWT token bilan kirgan foydalanuvchilar murojaat qila oladi
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # Bitta IP manzildan login'ga urinishlar soni
    "DEFAULT_THROTTLE_RATES": {
        "login": "5/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# Refresh token brauzerda httpOnly cookie'da saqlanadi (JavaScript o'qiy olmaydi)
REFRESH_COOKIE_NAME = "refresh_token"
# Cookie faqat kirish manzillariga yuboriladi
REFRESH_COOKIE_PATH = "/api/auth/"
# HTTPS'da (DEBUG=False) cookie faqat shifrlangan ulanish orqali yuboriladi
REFRESH_COOKIE_SECURE = not DEBUG

# Sun'iy intellekt (Anthropic API). Kalit bo'sh bo'lsa, AI funksiyalari kutish holatida turadi.
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
AI_MODEL = env("AI_MODEL", default="claude-sonnet-5-5")
# Bitta talaba kuniga yubora oladigan chat xabarlari soni
AI_CHAT_DAILY_LIMIT = env.int("AI_CHAT_DAILY_LIMIT", default=30)

# Telegram bildirishnomalari. Ikkalasi ham bo'sh bo'lmasa, bot ishlaydi.
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
# Bot nomi @ belgisisiz, masalan: dbproject_bot
TELEGRAM_BOT_USERNAME = env("TELEGRAM_BOT_USERNAME", default="")
