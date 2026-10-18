#!/bin/sh
# Brauzer testlarini (Playwright) ishga tushiradi. Har safar toza e2e bazasi bilan:
#   ./e2e.sh                       # hammasi
#   ./e2e.sh e2e/quiz.spec.ts      # bitta fayl (qo'shimcha argumentlar playwright test ga uzatiladi)
# Hisobot: frontend/playwright-report/index.html
set -e
cd "$(dirname "$0")"

compose() { docker compose -f docker-compose.yml -f docker-compose.e2e.yml "$@"; }

compose up -d --wait db lab_db
# Qayta yaratish: seed_e2e bazani noldan tayyorlaydi, login cheklovi hisoblagichi ham tozalanadi
compose up -d --wait --force-recreate --no-deps e2e_backend e2e_frontend

status=0
compose run --rm --no-deps e2e npx playwright test "$@" || status=$?

compose rm -sf e2e_backend e2e_frontend >/dev/null
exit $status
