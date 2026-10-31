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
docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --wait --force-recreate e2e-backend e2e-frontend
cd frontend && BASE_URL=http://127.0.0.1:4173 PW_CHANNEL=chrome npx playwright test
```

Qayta ishga tushirishdan oldin `up ... --force-recreate` ni takrorlang: baza toza bo'ladi (talaba testni
faqat bir marta topshira oladi) va login cheklovi (minutiga 5 ta) hisoblagichi ham tozalanadi.

## Pilot

`e2e/pilot.spec.ts` tajribaning butun yo'lini tekshiradi: rozilik, kirish testi, laboratoriya, chiqish testi, so'rovnoma
(tajriba va nazorat talabasi), keyin o'qituvchi tahlil kartasi va eksport. Natijalar `frontend/test-results/pilot/` da:
`statistika.png` va `eksport.zip`. Testlar haqiqiy AI ni chaqirmaydi: e2e muhitida kalitlar bo'sh.

## Test ma'lumotlari

`backend/users/management/commands/seed_e2e.py` yaratadi, loginlar `e2e/accounts.ts` da.
Buyruq faqat `E2E=1` bo'lsa va baza nomi `_e2e` bilan tugasa ishlaydi.

Login minutiga 5 marta bilan cheklangan, shuning uchun har bir rol uchun bir marta kiriladi
(`auth.setup.ts`) va sessiya `e2e/.auth/` da saqlanib boshqa testlarda qayta ishlatiladi.
Yangi test login qilsa, jami loginlar soni 5 dan oshmasligini kuzating.

Refresh token har yangilanishda almashtiriladi va eski nusxa qayta ishlatilsa server barcha sessiyalarni
yopadi. Shuning uchun saqlangan sessiya bilan ishlaydigan testlar `test` va `expect` ni `@playwright/test`
dan emas, `./fixtures.ts` dan oladi: test tugagach yangi cookie `e2e/.auth/` ga qayta yoziladi.
Saqlangan sessiyada "Chiqish" bosilmasin, aks holda keyingi testlar shu rol uchun kira olmaydi.

## Playwright'ni yangilash

Dependabot `@playwright/test` ni yangilamaydi: paket versiyasi (`package.json`, aniq versiya) va
`docker-compose.e2e.yml` dagi `mcr.microsoft.com/playwright:vX.Y.Z-noble` obrazi bir xil bo'lishi kerak.
Ikkalasini bitta PR'da birga o'zgartiring.
