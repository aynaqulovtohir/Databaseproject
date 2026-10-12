FROM docker.io/library/python:3.13-slim

# .pyc fayllar yozilmasin, loglar darhol chiqsin
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
