"""2-texnik tekshiruv: 20 ta sintetik hisob bir vaqtda kiradi va kirish (A/B), chiqish (B/A), kechiktirilgan testlarni
hamda imtihon rejimidagi uchta AI'siz ER topshirig'ini bajaradi. Login 429 javoblari sanaladi.

    python3 tekshiruv2_ishga_tushirish.py tekshiruv2.json | tee natijalar/tekshiruv2.log
"""
import json
import sys
import threading

import api
import sintetik as s

setup = json.loads(open(sys.argv[1], encoding="utf-8").read().strip().splitlines()[-1])
s.KEYS = {int(k): v for k, v in setup["keys"].items()}
s.REF = {int(k): v for k, v in setup["refs"].items()}
s.LABS = setup["labs"]
s.PRE_SKILL = {
    "SIM2-Tajriba-A": [0.25, 0.45, 0.55, 0.70, 0.85], "SIM2-Tajriba-B": [0.30, 0.40, 0.60, 0.65, 0.80],
    "SIM2-Nazorat-A": [0.30, 0.40, 0.55, 0.70, 0.80], "SIM2-Nazorat-B": [0.25, 0.45, 0.50, 0.65, 0.85],
}
throttled = []
original_call = api.call


def counting_call(method, path, token=None, data=None):
    status, payload = original_call(method, path, token, data)
    if path == "auth/login/" and status == 429:
        throttled.append(data["username"])
    return status, payload


api.call = counting_call
local = threading.local()


class QuizIds(dict):
    """Har bir talaba o'z variantidagi testlarni oladi (oqim bo'yicha)."""

    def __getitem__(self, kind):
        return local.quizzes[kind]


s.QUIZ = QuizIds()
OTHER = {"A": "B", "B": "A"}


def run(username, password, group, form, seed):
    local.quizzes = {"pre": setup["quizzes"][f"pre-{form}"], "post": setup["quizzes"][f"post-{OTHER[form]}"],
                     "delayed": setup["quizzes"][f"delayed-{form}"]}
    s.student(username, password, group, int(username[-1]) - 1, seed)


threads = [threading.Thread(target=run, args=(u, p, g, f, 2000 + n)) for n, (u, p, g, f) in enumerate(setup["creds"])]
for t in threads:
    t.start()
for t in threads:
    t.join()
print("LOGIN 429 SONI:", len(throttled), sorted(set(throttled)))
