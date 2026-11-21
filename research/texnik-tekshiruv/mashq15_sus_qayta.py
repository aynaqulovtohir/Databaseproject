"""Faqat SUS (T7) bosqichini 15 ta hisob bilan bir vaqtda qayta bajaradi (2026-11-21: umumiy SUS so'rovnomasi vaqti
yopiq bo'lgani uchun birinchi ishga tushirishda T7 HTTP 400 qaytargan). python3 mashq15_sus_qayta.py mashq15.json"""
import json, sys, random, threading, collections, api
S = json.loads(open(sys.argv[1]).read().strip().splitlines()[-1]); SUS = S["sus"]
st = collections.Counter(); lock = threading.Lock()
def run(u, p, name, idx):
    rnd = random.Random(500 + idx)
    for _ in range(14): rnd.random()
    t = api.login(u, p)
    s, d = api.call("POST", f"quizzes/{SUS}/start/", t)
    answers = {}
    for n, q in enumerate(d["questions"], 1):
        ids = [c["id"] for c in q["choices"]]
        v = rnd.choices([2,3,4,5],[1,3,5,3])[0] if n % 2 else rnd.choices([1,2,3,4],[3,5,3,1])[0]
        if not (u == "fs15_11" and n == 10): answers[str(q["id"])] = [ids[v-1]]
    s2, _ = api.call("POST", f"quizzes/{SUS}/submit/", t, {"answers": answers})
    with lock: st[s]+=1; st[s2]+=1; print(u, "start", s, "submit", s2, f"{len(answers)}/10", flush=True)
th = [threading.Thread(target=run, args=(*c, i)) for i, c in enumerate(S["creds"])]
[x.start() for x in th]; [x.join() for x in th]; print("HTTP:", dict(st))
