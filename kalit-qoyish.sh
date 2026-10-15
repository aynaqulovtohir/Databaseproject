#!/bin/sh
# Gemini API kalitini .env fayliga yozadi va xizmatlarni qayta ishga tushiradi.
# Ishlatish: sh kalit-qoyish.sh
cd "$(dirname "$0")" || exit 1
ENV_FILE="${ENV_FILE:-.env}"

printf "Gemini kalitini yopishtiring (Ctrl+Shift+V) va Enter bosing. Kalit ekranda ko'rinmaydi: "
stty -echo 2>/dev/null
read -r KEY
stty echo 2>/dev/null
echo

if [ -z "$KEY" ]; then
    echo "Kalit kiritilmadi. Hech narsa o'zgarmadi."
    exit 1
fi

KEY="$KEY" python3 - "$ENV_FILE" <<'PY' || exit 1
import os, sys

path = sys.argv[1]
key = os.environ["KEY"].strip()
lines = open(path, encoding="utf-8").read().splitlines()
values = {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": key}
seen = set()
for index, line in enumerate(lines):
    name = line.split("=", 1)[0]
    if name in values:
        lines[index] = f"{name}={values[name]}"
        seen.add(name)
lines += [f"{name}={value}" for name, value in values.items() if name not in seen]
open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print(f"Kalit {path} fayliga yozildi ({len(key)} belgi).")
PY

if [ -z "$SKIP_RESTART" ]; then
    echo "Xizmatlar qayta ishga tushirilmoqda..."
    podman compose up -d && echo "Tayyor. Endi Claude'ga \"kalitni qo'ydim\" deb yozing."
fi
