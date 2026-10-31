#!/bin/sh
# Loyihani kompyuterda (localhost) boshqarish:
#   sh loyiha.sh            # GitHub'dan yangi kodni olib ishga tushirish (= start, = yangilash); internet bo'lmasa — mavjud kod bilan
#   sh loyiha.sh holat      # qaysi qismlar ishlayapti
#   sh loyiha.sh log        # server xatolari (chiqish: Ctrl+C); sh loyiha.sh log frontend — sayt xatolari
#   sh loyiha.sh stop       # to'xtatish (ma'lumotlar o'chmaydi)
# --oyna (papkadagi yorliqdan): tayyor bo'lgach brauzer ochiladi, oyna Enter bosilguncha yopilmaydi
cd "$(dirname "$0")" || exit 1

if [ "$2" = "--oyna" ]; then
    trap 'echo; printf "Oynani yopish uchun Enter bosing..."; read _' EXIT
fi

# GitHub'dan yangi kod: hech qachon ishga tushirishni to'xtatmaydi, faqat ogohlantiradi. Faqat oldinga (fast-forward)
# yangilanadi, saqlanmagan o'zgarishlarga tegmaydi. Branch main'ga to'liq birlashtirilgan bo'lsa, main'ga o'tiladi.
yangi_kod() {
    if ! GIT_TERMINAL_PROMPT=0 GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=10" timeout 30 git fetch -q origin 2>/dev/null; then
        echo "   Diqqat: GitHub'ga ulanib bo'lmadi (internet?). Kompyuterdagi kod bilan davom etiladi."
        return 0
    fi
    if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
        echo "   Diqqat: saqlanmagan o'zgarishlar bor, kod yangilanmadi (git status)."
        return 0
    fi
    branch=$(git branch --show-current)
    if [ -z "$branch" ]; then
        echo "   Diqqat: kod hech qaysi branchda emas, yangilanmadi."
        return 0
    fi
    if [ "$branch" != main ]; then
        if git merge-base --is-ancestor HEAD origin/main; then
            git switch -q main || {
                echo "   Diqqat: main'ga o'tib bo'lmadi, $branch branchida qolindi."
                return 0
            }
            echo "   $branch birlashtirilgan: main'ga o'tildi."
        else
            echo "   Diqqat: $branch branchi hali main'ga birlashtirilmagan, shu branchda qolindi."
        fi
    fi
    git merge -q --ff-only "@{upstream}" 2>/dev/null || echo "   Diqqat: kodni yangilab bo'lmadi (git status), mavjud kod bilan davom etiladi."
}

xesh() {
    cat "$@" 2>/dev/null | sha256sum | cut -d" " -f1
}

# O'rnatilgan holat .git ichida saqlanadi: o'rnatish muvaffaqiyatsiz bo'lsa, keyingi safar yana uriniladi
holat_oqi() {
    sed -n "$1p" "$HOLAT" 2>/dev/null
}

holat_yoz() {
    printf '%s\n%s\n%s\n' "$ESKI_PY" "$ESKI_JS" "$ESKI_KOD" > "$HOLAT"
}

# Kutubxonalar o'zgargan bo'lsa o'rnatiladi; bo'lmasa (internet yo'q) — ogohlantirib, mavjudlari bilan davom etiladi
kutubxonalar() {
    HOLAT="$(git rev-parse --git-dir)/loyiha-holat"
    ESKI_PY=$(holat_oqi 1)
    ESKI_JS=$(holat_oqi 2)
    ESKI_KOD=$(holat_oqi 3)
    YANGI_JS=0
    py=$(xesh backend/requirements.txt backend/Dockerfile)
    if [ "$py" != "$ESKI_PY" ]; then
        echo "   Python kutubxonalari o'rnatilmoqda..."
        if docker compose build; then
            ESKI_PY=$py
        else
            echo "   Diqqat: Python kutubxonalarini o'rnatib bo'lmadi, keyingi safar yana uriniladi."
        fi
    fi
    js=$(xesh frontend/package.json frontend/package-lock.json)
    if [ "$js" != "$ESKI_JS" ]; then
        echo "   Sayt kutubxonalari o'rnatilmoqda..."
        if docker compose run --rm --no-deps -T frontend npm install --no-save --no-audit --no-fund; then
            ESKI_JS=$js
            YANGI_JS=1
        else
            echo "   Diqqat: sayt kutubxonalarini o'rnatib bo'lmadi, keyingi safar yana uriniladi."
        fi
    fi
    holat_yoz
}

# AI worker va Telegram bot kodni o'zi qayta yuklamaydi: kod o'zgargan bo'lsa, qayta ishga tushiriladi.
# Sayt yangi kutubxonalarni faqat qayta ishga tushganda oladi
qayta_yuklash() {
    kod=$(git rev-parse HEAD)
    if [ "$kod" != "$ESKI_KOD" ]; then
        docker compose restart ai_worker telegram_bot >/dev/null 2>&1 || echo "   Diqqat: AI worker va Telegram botni qayta ishga tushirib bo'lmadi."
        ESKI_KOD=$kod
        holat_yoz
    fi
    if [ "$YANGI_JS" = 1 ]; then
        docker compose restart frontend >/dev/null 2>&1 || echo "   Diqqat: saytni qayta ishga tushirib bo'lmadi."
    fi
}

start() {
    echo "1/4. Yangi kod tekshirilmoqda..."
    yangi_kod
    kutubxonalar

    echo "2/4. Xizmatlar ishga tushirilmoqda..."
    docker compose up -d || exit 1
    qayta_yuklash

    echo "3/4. Ma'lumotlar bazasi yangi kodga moslanmoqda (migratsiya)..."
    docker compose exec -T backend python manage.py migrate --noinput || {
        echo "Migratsiya bajarilmadi. Xatoni ko'rish: sh loyiha.sh log"
        exit 1
    }

    echo "4/4. Sayt yuklanishi kutilmoqda..."
    for _ in $(seq 1 60); do
        if curl -s -o /dev/null http://127.0.0.1:5173/; then
            echo
            echo "Tayyor: http://localhost:5173"
            echo "To'xtatish: sh loyiha.sh stop"
            [ "$2" = "--oyna" ] && xdg-open http://localhost:5173 >/dev/null 2>&1
            return 0
        fi
        sleep 2
    done
    echo "Sayt 2 daqiqada ochilmadi. Xatoni ko'rish: sh loyiha.sh log frontend"
    exit 1
}

case "${1:-start}" in
    start | yangilash)
        start "$@"
        ;;
    holat)
        docker compose ps
        ;;
    log)
        docker compose logs -f --tail 50 "${2:-backend}"
        ;;
    stop)
        docker compose stop
        echo "To'xtatildi. Qayta ishga tushirish: sh loyiha.sh"
        ;;
    *)
        echo "Noma'lum buyruq: $1"
        echo "Ishlatish: sh loyiha.sh [start | yangilash | holat | log [backend|frontend] | stop]"
        exit 1
        ;;
esac
