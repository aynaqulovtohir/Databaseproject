"""Nazorat guruhida (AI o'chirilgan) AI funksiyalari bloklanishini tekshiradi: maslahat, murabbiy, yechimni
tushuntirish, AI buyurtmachi (HTTP 403) va o'qish tavsiyasi (AI'siz, qoidalar asosida). AI chaqirilmaydi.

    python3 ai_bloklash_sinovi.py tekshiruv2.json | tee natijalar/ai_bloklash_sinovi.txt
"""
import json
import sys

from api import call, login

data = json.loads(open(sys.argv[1], encoding="utf-8").read().strip().splitlines()[-1])
lab = data["learn"]
ref = data["refs"][str(lab)]
control = [(u, p) for u, p, g, _ in data["creds"] if g.startswith("SIM2-Nazorat")][:2]
wrong = {"entities": ref["entities"][:2], "relationships": []}

for username, password in control:
    token = login(username, password)
    status, run = call("POST", f"labs/{lab}/run/", token, {"diagram": wrong})
    print(f"{username}: tekshirish HTTP {status}, ai_available={run.get('ai_available')}, ai_explain={run.get('ai_explain')}")
    checks = [
        ("maslahat", "POST", f"labs/attempts/{run['attempt_id']}/advice/", {"level": 1}),
        ("murabbiy", "POST", f"labs/{lab}/chat/", {"content": "yordam bering"}),
        ("AI buyurtmachi", "POST", f"labs/{lab}/interview/", {"message": "salom"}),
    ]
    for name, method, path, body in checks:
        status, payload = call(method, path, token, body)
        print(f"  {name:16} HTTP {status}  {str(payload)[:80]}")
    # O'qish tavsiyasi: kamida 2 noto'g'ri urinishdan keyin; nazorat guruhida AI'siz (manba: rules)
    call("POST", f"labs/{lab}/run/", token, {"diagram": {"entities": ref["entities"][:1], "relationships": []}})
    status, _ = call("POST", f"labs/{lab}/study-advice/", token, {})
    _, advice = call("GET", f"labs/{lab}/study-advice/", token)
    print(f"  {'o`qish tavsiyasi':16} HTTP {status}, AI ishlatilganmi: {advice.get('ai') if isinstance(advice, dict) else '?'}")
    # Yechimni tushuntirish: faqat to'g'ri yechimdan keyin so'raladi
    status, correct = call("POST", f"labs/{lab}/run/", token, {"diagram": ref})
    status, payload = call("POST", f"labs/attempts/{correct['attempt_id']}/explain/", token,
                           {"text": "Bu yechimda hodisa alohida obyekt, chunki uning o'z sanalari bor va ikki obyektga bog'lanadi."})
    print(f"  {'tushuntirish':16} HTTP {status}  {str(payload)[:80]}")
