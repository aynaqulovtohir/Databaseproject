# Platformani internetga chiqarish

Platforma bitta serverda Docker konteynerlarida ishlaydi:

| Xizmat | Vazifasi |
|---|---|
| `web` | Caddy: frontend, HTTPS (Let's Encrypt sertifikati avtomatik olinadi va yangilanadi), xavfsizlik sarlavhalari |
| `backend` | Django + gunicorn (API va admin) |
| `db` | Asosiy PostgreSQL bazasi |
| `lab_db` | Talabalar SQL kodi bajariladigan alohida, resurslari cheklangan PostgreSQL (pgvector kengaytmasi bilan: vektorli qidiruv laboratoriyalari uchun) |
| `ai_worker`, `telegram_bot` | Fon jarayonlari: AI tahlili va Telegram bildirishnomalari; bot har daqiqada backend va bazalarni tekshiradi va nosozlik bo'lsa Telegram'ni bog'lagan adminlarga yozadi |
| `backup` | Har kuni baza va yuklangan fayllarning zaxira nusxasi (`./backups`) |

Tashqariga faqat 80 va 443 portlar ochiladi. Baza va backend ichki tarmoqda.

## 1. Kerakli narsalar

- **Server (VPS)**: Ubuntu 24.04, kamida 2 CPU, 4 GB RAM, 20 GB disk.
- **Domen**: masalan, `mb.example.uz`. DNS'da A-yozuv server IP manziliga qaratilgan bo'lsin
  (tekshirish: `ping mb.example.uz` server IP'sini ko'rsatishi kerak).
- **Gemini API kaliti** (https://aistudio.google.com/apikey).

## 2. Serverni tayyorlash

```sh
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-v2 git ufw unattended-upgrades
sudo usermod -aG docker $USER        # keyin serverdan chiqib, qayta kiring

# Faqat SSH, HTTP va HTTPS ochiq
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443
sudo ufw enable
```

## 3. Kodni olish

Repozitoriy yopiq (private), shuning uchun serverga faqat o'qish huquqli kalit bering:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N ""
cat ~/.ssh/github_deploy.pub
```

Chiqqan kalitni GitHub'da: repozitoriy → **Settings → Deploy keys → Add deploy key** (**Allow write access** belgilanmasin).

```sh
GIT_SSH_COMMAND="ssh -i ~/.ssh/github_deploy" git clone git@github.com:aynaqulovtohir/Databaseproject.git
cd Databaseproject
git config core.sshCommand "ssh -i ~/.ssh/github_deploy"
```

## 4. Sozlamalar (.env)

```sh
cp .env.production.example .env
chmod 600 .env
nano .env
```

To'ldirilishi shart: `DOMAIN`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SECRET_KEY`, `POSTGRES_PASSWORD`,
`LAB_DB_PASSWORD`, `GEMINI_API_KEY`. Parol va kalitlarni tasodifiy yarating:

```sh
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

## 5. Ishga tushirish

```sh
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps        # hammasi "running" / "healthy" bo'lishi kerak
```

Birinchi ishga tushirishda Caddy sertifikat oladi (bir necha soniya). Brauzerda `https://DOMAIN` ni oching.

## 6. Birinchi administrator va laboratoriyalar

```sh
# Administrator (parolni so'raydi)
docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser

# Administrator sifatida saytga kirib, guruh, o'qituvchi va talabalarni yarating. Keyin tayyor
# loyihalash laboratoriyalarini (3 ta ER-model va 7 ta SQL) o'qituvchi va guruhga qo'shing:
docker compose -f docker-compose.prod.yml exec backend \
    python manage.py seed_design_labs --author <o'qituvchi_logini> --group "<guruh nomi>"
```

## 7. Yangilash (yangi versiyani o'rnatish)

```sh
cd Databaseproject
docker compose -f docker-compose.prod.yml exec backup bash /backup.sh once   # avval zaxira nusxa
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Baza migratsiyalari backend ishga tushganda avtomatik bajariladi.

## 8. Zaxira nusxa va tiklash

Nusxalar `./backups` papkasida: `baza-SANA.sql.gz` (baza) va `fayllar-SANA.tar.gz` (yuklangan materiallar).
Ular har kuni va har safar konteyner qayta ishga tushganda olinadi, 14 kundan eskilari o'chiriladi
(`BACKUP_KEEP_DAYS`). **Nusxalarni muntazam boshqa joyga ham ko'chiring** (server buzilsa, ular ham yo'qoladi):

```sh
scp server:Databaseproject/backups/baza-*.sql.gz ./
```

Bazani nusxadan tiklash (joriy ma'lumotlar o'chadi):

```sh
docker compose -f docker-compose.prod.yml stop backend ai_worker telegram_bot
docker compose -f docker-compose.prod.yml exec db sh -c 'dropdb -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
gunzip -c backups/baza-SANA.sql.gz | docker compose -f docker-compose.prod.yml exec -T db sh -c 'psql -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose -f docker-compose.prod.yml start backend ai_worker telegram_bot
```

Yuklangan fayllarni tiklash:

```sh
docker run --rm -v mb-platforma_media_data:/media -v "$PWD/backups:/backups" docker.io/library/alpine \
    sh -c 'rm -rf /media/* && tar -xzf /backups/fayllar-SANA.tar.gz -C /media && chown -R 10001 /media'
```

## 9. Loglar va nazorat

```sh
docker compose -f docker-compose.prod.yml logs -f backend          # API so'rovlari va xatolar
docker compose -f docker-compose.prod.yml logs -f web              # Caddy (HTTPS, sertifikat)
docker compose -f docker-compose.prod.yml logs --tail 50 backup    # zaxira nusxalar
```

## Xavfsizlik bo'yicha eslatmalar

- `.env` faqat serverda turadi, `chmod 600`. Uni git'ga, chatga yoki xatga qo'shmang.
- Serverga SSH kalit bilan kiring, parol bilan kirishni o'chiring (`PasswordAuthentication no`).
- `unattended-upgrades` xavfsizlik yangilanishlarini avtomatik o'rnatadi.
- HTTPS to'g'ri ishlashiga ishonch hosil qilgach `HSTS_MAX_AGE=31536000` qoldiring: brauzerlar saytni faqat
  HTTPS orqali ochadi.
- Talabalar SQL kodi `lab_db` da bajariladi: u asosiy bazadan ajratilgan, internetga chiqmaydi va xotira/CPU/disk
  bilan cheklangan.
- Login'ga bitta IP'dan daqiqasiga 5 ta urinish mumkin (Caddy orqali foydalanuvchining haqiqiy IP'si aniqlanadi).
