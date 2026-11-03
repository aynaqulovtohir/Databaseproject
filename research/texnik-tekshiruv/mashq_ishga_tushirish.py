"""Foydalanish sinovi MASHQI: 12 ta sintetik hisob protokoldagi T1–T7 ni bir vaqtda bajaradi. To'rt hisob ataylab
bittadan topshiriqni o'tkazib yuboradi (hisobot ularni aniqlay olishini tekshirish uchun). Sintetik SUS javoblari
talqin qilinmaydi. O'quv laboratoriyasida AI (maslahat, murabbiy, AI baholash) haqiqatan chaqiriladi.

    python3 mashq_ishga_tushirish.py mashq.json | tee natijalar/mashq.log
Keyin hisobot: python manage.py usability_report --group FS-MASHQ --learn-lab <id> --exam-lab <id> --sus <id>
"""
import collections, json, random, sys, threading, time
import api
import sintetik as rs

S = json.loads(open(sys.argv[1], encoding="utf-8").read().strip().splitlines()[-1])
LEARN, EXAM, SUS = S["learn"], S["exam"], S["sus"]
REF = {LEARN: S["learn_ref"], EXAM: S["exam_ref"]}
statuses = collections.Counter()
lock = threading.Lock()
orig = api.call


def call(method, path, token=None, data=None):
    s, d = orig(method, path, token, data)
    with lock:
        statuses[s // 100 * 100] += 1
        if s >= 500:
            print(f"  !! {s} {method} {path} {str(d)[:120]}", flush=True)
    return s, d


api.call = call
SKIP = {"fs_07": "T3", "fs_04": "T4", "fs_09": "T6", "fs_11": "T7"}
COACH = {"fs_02", "fs_06"}
QUESTIONS = {"fs_02": "Ijara alohida obyekt bo'lishi kerakmi yoki Kitob va Kitobxon orasidagi bog'lanishmi?",
             "fs_06": "Muallif va Kitob orasidagi bog'lanish 1:N mi yoki M:N?"}


def log(u, m):
    with lock:
        print(f"[{time.strftime('%H:%M:%S')}] {u}: {m}", flush=True)


def snap(t, lab, diagram):
    call("POST", f"labs/{lab}/er-snapshot/", t, {"diagram": diagram})
    time.sleep(3.2)


def student(username, password, name, idx):
    rnd = random.Random(500 + idx)
    skill = [0.45, 0.6, 0.75, 0.55, 0.85, 0.5, 0.65, 0.7, 0.4, 0.8, 0.6, 0.7][idx]
    skip = SKIP.get(username)
    try:
        time.sleep(idx * 0.5)
        t = api.login(username, password)                                   # T1
        call("POST", "auth/consent/", t, {"agreed": True})
        log(username, f"{name} kirdi")
        # T2–T5: o'quv laboratoriyasi
        ents, rels = rs.target_diagram(REF[LEARN], skill, rnd)
        seq = rs.states(ents, rels, "mixed", rnd)
        half = max(1, len(seq) // 2)
        for diagram in seq[:half]:
            snap(t, LEARN, diagram)
        if skip != "T3":
            s, d = call("POST", f"labs/{LEARN}/run/", t, {"diagram": seq[half - 1], "confidence": rnd.randint(2, 4)})
            first_ratio, attempt = d.get("ratio"), d.get("attempt_id")
            if skip != "T4" and not d.get("is_correct"):
                if username in COACH:
                    s2, _ = call("POST", f"labs/{LEARN}/chat/", t, {"content": QUESTIONS[username], "diagram": seq[half - 1]})
                    log(username, f"murabbiyga savol: HTTP {s2}")
                else:
                    s2, d2 = call("POST", f"labs/attempts/{attempt}/advice/", t, {"level": 1})
                    log(username, f"1-darajali maslahat: HTTP {s2}")
        for diagram in seq[half:]:
            snap(t, LEARN, diagram)
        if skip != "T3":
            s, d = call("POST", f"labs/{LEARN}/run/", t, {"diagram": seq[-1], "confidence": rnd.randint(3, 5)})
            log(username, f"qayta tekshirish: moslik {first_ratio} → {d.get('ratio')}")
        s, d = call("POST", f"labs/{LEARN}/submit/", t, {"diagram": seq[-1], "confidence": rnd.randint(3, 5)})
        log(username, f"o'quv lab topshirildi: {d.get('grade', {}).get('score')} ({d.get('grade', {}).get('source')})")
        # T6: imtihon rejimidagi topshiriq
        ents, rels = rs.target_diagram(REF[EXAM], skill - 0.05, rnd)
        seq = rs.states(ents, rels, "objects_first", rnd)
        for diagram in seq:
            snap(t, EXAM, diagram)
        if skip != "T6":
            s, d = call("POST", f"labs/{EXAM}/submit/", t, {"diagram": seq[-1], "confidence": rnd.randint(2, 5)})
            log(username, f"imtihon topshirildi: {d.get('grade', {}).get('score')} ({d.get('grade', {}).get('source')}), tuzatilgan ko'rsatildi: {bool(d.get('fix'))}")
        else:
            log(username, "imtihon topshirig'ini topshirmadi")
        # T7: SUS
        s, d = call("POST", f"quizzes/{SUS}/start/", t)
        answers = {}
        for n, q in enumerate(d["questions"], 1):
            ids = [c["id"] for c in q["choices"]]
            value = rnd.choices([2, 3, 4, 5], [1, 3, 5, 3])[0] if n % 2 else rnd.choices([1, 2, 3, 4], [3, 5, 3, 1])[0]
            if not (skip == "T7" and n == 10):
                answers[str(q["id"])] = [ids[value - 1]]
        s, d = call("POST", f"quizzes/{SUS}/submit/", t, {"answers": answers})
        log(username, f"SUS topshirildi ({len(answers)}/10)")
    except Exception as exc:  # noqa: BLE001
        log(username, f"XATO: {exc}")


threads = [threading.Thread(target=student, args=(*c, i)) for i, c in enumerate(S["creds"])]
[t.start() for t in threads]
[t.join() for t in threads]
print("HTTP holatlari:", dict(statuses))
