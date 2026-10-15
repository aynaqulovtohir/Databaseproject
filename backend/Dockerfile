FROM docker.io/library/python:3.13-slim AS base

# .pyc fayllar yozilmasin, loglar darhol chiqsin
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Ishchi server (docker-compose.prod.yml): ilova root huquqisiz foydalanuvchi nomidan ishlaydi.
# Migratsiya, statik fayllar va gunicorn entrypoint.sh da ishga tushiriladi.
FROM base AS production
RUN useradd --system --uid 10001 --no-create-home --home-dir /app app \
    && mkdir -p /app/media /app/staticfiles \
    && chown app /app/media /app/staticfiles
USER app
CMD ["sh", "/app/entrypoint.sh"]

# Ishlab chiqish (docker-compose.yml) — oxirgi bosqich, target ko'rsatilmasa shu quriladi
FROM base AS development
