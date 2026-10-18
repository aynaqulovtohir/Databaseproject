# Brauzer testlari (Playwright)

Foydalanuvchi ko'zi bilan tekshiradi: login, menyudagi har bir sahifa (har bir rol uchun), ruxsatlar,
tadqiqotga rozilik, test topshirish. Production yig'masi (`vite build`) ishlatiladi.

## Ishga tushirish

Loyiha ildizidan:

```sh
./e2e.sh                       # hammasi
./e2e.sh e2e/quiz.spec.ts      # bitta fayl (argumentlar `playwright test` ga uzatiladi)
```

Skript alohida `dbproject_e2e` bazasini noldan yaratadi (`seed_e2e`), test backend'i va frontend'ini
ko'taradi, Playwright konteynerida testlarni bajaradi va test konteynerlarini o'chiradi.
Ishlab chiqish bazasiga tegilmaydi. Birinchi marta Playwright obrazi (~2 GB) yuklanadi.

Hisobot: `frontend/playwright-report/index.html`, yiqilgan testlarning skrinshoti va izi: `frontend/test-results/`.

### Konteynersiz (Node va Google Chrome o'rnatilgan bo'lsa)

```sh
docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --wait --force-recreate e2e_backend e2e_frontend
cd frontend && BASE_URL=http://127.0.0.1:4173 PW_CHANNEL=chrome npx playwright test
```

Qayta ishga tushirishdan oldin `up ... --force-recreate` ni takrorlang: baza toza bo'ladi (talaba testni
faqat bir marta topshira oladi) va login cheklovi (minutiga 5 ta) hisoblagichi ham tozalanadi.

## Test ma'lumotlari

`backend/users/management/commands/seed_e2e.py` yaratadi, loginlar `e2e/accounts.ts` da.
Buyruq faqat `E2E=1` bo'lsa va baza nomi `_e2e` bilan tugasa ishlaydi.

Login minutiga 5 marta bilan cheklangan, shuning uchun har bir rol uchun bir marta kiriladi
(`auth.setup.ts`) va sessiya `e2e/.auth/` da saqlanib boshqa testlarda qayta ishlatiladi.
Yangi test login qilsa, jami loginlar soni 5 dan oshmasligini kuzating.
