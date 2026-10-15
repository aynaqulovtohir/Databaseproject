#!/bin/bash
# Zaxira nusxa: baza (pg_dump) va yuklangan fayllar. docker-compose.prod.yml dagi backup xizmati ishga tushiradi:
# ishga tushganda va keyin har kuni nusxa oladi, BACKUP_KEEP_DAYS kundan eskilarini o'chiradi.
# Qo'lda bir marta nusxa olish (masalan, yangilashdan oldin):
#   docker compose -f docker-compose.prod.yml exec backup bash /backup.sh once
set -o pipefail

backup() {
    local stamp database files
    stamp=$(date +%Y-%m-%d_%H%M%S)
    database="/backups/baza-$stamp.sql.gz"
    files="/backups/fayllar-$stamp.tar.gz"
    if PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner \
        | gzip > "$database.tmp"; then
        mv "$database.tmp" "$database"
        echo "$(date) Baza zaxirasi: $database"
    else
        rm -f "$database.tmp"
        echo "$(date) XATO: baza zaxirasini olib bo'lmadi" >&2
    fi
    if tar -czf "$files.tmp" -C /media . ; then
        mv "$files.tmp" "$files"
        echo "$(date) Fayllar zaxirasi: $files"
    else
        rm -f "$files.tmp"
        echo "$(date) XATO: fayllar zaxirasini olib bo'lmadi" >&2
    fi
    find /backups -name 'baza-*.sql.gz' -mtime "+${BACKUP_KEEP_DAYS:-14}" -delete
    find /backups -name 'fayllar-*.tar.gz' -mtime "+${BACKUP_KEEP_DAYS:-14}" -delete
}

if [ "$1" = "once" ]; then
    backup
    exit
fi

while true; do
    backup
    sleep 86400
done
