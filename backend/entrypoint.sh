#!/bin/sh
# Ishchi serverda backend'ni ishga tushirish: migratsiya, kesh jadvali, statik fayllar, gunicorn.
set -e

python manage.py migrate --noinput
python manage.py createcachetable
python manage.py collectstatic --noinput --verbosity 0

# gthread: AI so'rovlari (bir necha o'n soniya) kutilayotganda ham boshqa so'rovlar xizmat qilinadi.
# timeout AI'ning eng uzun kutishidan (asosiy va zaxira modellar) katta.
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --threads 4 \
    --timeout 240 \
    --access-logfile -
