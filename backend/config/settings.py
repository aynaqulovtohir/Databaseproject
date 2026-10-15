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
    "labs",
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
        # Bitta foydalanuvchi laboratoriyada kodni ishga tushirish soni
        "lab_run": "30/min",
        # Bitta talaba laboratoriyani baholashga topshirish soni
        "lab_submit": "6/min",
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
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
# HTTPS majburiyligi: sayt faqat HTTPS orqali ishlashi aniq bo'lgandan keyin .env da yoqiladi
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0)

# Sun'iy intellekt. AI_PROVIDER qaysi xizmat ishlatilishini belgilaydi: "anthropic" yoki "gemini".
# Tanlangan xizmat kaliti bo'sh bo'lsa, AI funksiyalari kutish holatida turadi.
AI_PROVIDER = env("AI_PROVIDER", default="anthropic").strip().lower()
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
AI_MODEL = env("AI_MODEL", default="claude-sonnet-5-5")
GEMINI_API_KEY = env("GEMINI_API_KEY", default="")
GEMINI_MODEL = env("GEMINI_MODEL", default="gemini-3.5-flash")
# Asosiy model band bo'lsa (bepul tarifda tez-tez uchraydi), navbat bilan sinaladigan modellar
GEMINI_FALLBACK_MODELS = env.list("GEMINI_FALLBACK_MODELS", default=["gemini-3.5-flash-lite", "gemini-3.7-flash"])
# Bitta talaba kuniga yubora oladigan chat xabarlari soni
AI_CHAT_DAILY_LIMIT = env.int("AI_CHAT_DAILY_LIMIT", default=30)

# Virtual laboratoriya: talaba SQL kodi shu alohida bazada bajariladi (o'zi yaratiladi)
LAB_SANDBOX_DB = env("LAB_SANDBOX_DB", default="lab_sandbox")
# Qum quti joylashgan Postgres serveri. Xavfsizlik uchun asosiy bazadan alohida server
# (docker-compose'dagi lab_db) tavsiya etiladi: talaba kodi serverni band qilsa ham
# platforma ishlayveradi. LAB_DB_HOST bo'sh bo'lsa, asosiy baza serveri ishlatiladi.
LAB_DB = {
    "HOST": env("LAB_DB_HOST", default="") or DATABASES["default"]["HOST"],
    "PORT": env("LAB_DB_PORT", default="") or DATABASES["default"]["PORT"],
    "USER": env("LAB_DB_USER", default="") or DATABASES["default"]["USER"],
    "PASSWORD": env("LAB_DB_PASSWORD", default="") or DATABASES["default"]["PASSWORD"],
    # Qum quti bazasi hali yo'q bo'lsa, uni yaratish uchun ulaniladigan baza
    "MAINTENANCE_DB": "postgres" if env("LAB_DB_HOST", default="") else DATABASES["default"]["NAME"],
}
# Bitta talaba kuniga oladigan AI maslahatlari soni
LAB_AI_DAILY_LIMIT = env.int("LAB_AI_DAILY_LIMIT", default=40)
# Bitta talabaning kuniga AI baholaydigan topshirishlari soni (undan keyin avtomatik baho qo'yiladi)
LAB_AI_GRADES_DAILY_LIMIT = env.int("LAB_AI_GRADES_DAILY_LIMIT", default=20)

# Telegram bildirishnomalari. Ikkalasi ham bo'sh bo'lmasa, bot ishlaydi.
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
# Bot nomi @ belgisisiz, masalan: dbproject_bot
TELEGRAM_BOT_USERNAME = env("TELEGRAM_BOT_USERNAME", default="")
