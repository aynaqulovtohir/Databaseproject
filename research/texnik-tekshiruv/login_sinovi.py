"""Auditoriya sharoiti: bitta IP manzildan 40 ta login so'rovi bir vaqtda (tekshiruv2.json dagi 20 hisob, har biri
ikki marta). Login cheklovi login nomiga bog'langani uchun HTTP 429 bo'lmasligi kerak.

    python3 login_sinovi.py tekshiruv2.json | tee natijalar/login_sinovi.txt
"""
import json
import sys
import threading
import time

from api import call

data = json.loads(open(sys.argv[1], encoding="utf-8").read().strip().splitlines()[-1])
creds = [(u, p) for u, p, *_ in data["creds"]]
requests = (creds * 2)[:40]
statuses, lock = [], threading.Lock()


def go(username, password):
    status, _ = call("POST", "auth/login/", data={"username": username, "password": password})
    with lock:
        statuses.append(status)


start = time.time()
threads = [threading.Thread(target=go, args=pair) for pair in requests]
for t in threads:
    t.start()
for t in threads:
    t.join()
print(f"{len(statuses)} ta login, {time.time() - start:.1f} s; holatlar: { {s: statuses.count(s) for s in sorted(set(statuses))} }")
