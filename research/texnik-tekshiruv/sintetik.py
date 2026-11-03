"""Sintetik talabalar simulyatsiyasi (texnik tekshiruv uchun): API orqali login, rozilik, testlar, AI'siz ER
topshiriqlari va so'rovnoma.

Sintetik ma'lumot: guruhlar orasida oldindan qo'yilgan farq YO'Q — chiqish darajasi ikkala shartda bir xil qoida bilan
hisoblanadi: boshlang'ich + 0,20 × (1 − boshlang'ich) + N(0; 0,07) shovqin. Natijalar o'quv samaradorligi haqida
xulosa uchun ishlatilmaydi, faqat platformaning hisoblash zanjirini tekshiradi.
"""
import copy
import random
import threading
import time

from api import call, login

STRATEGIES = ["objects_first", "mixed", "trial", "objects_first", "mixed"]
# Chaqiruvchi skript to'ldiradi: {guruh: [5 ta boshlang'ich daraja]}, javoblar kaliti, namunaviy diagrammalar,
# laboratoriyalar va testlar id'lari
PRE_SKILL = {}
KEYS, REF, LABS, QUIZ = {}, {}, {}, {}
log_lock = threading.Lock()


def log(user, msg):
    with log_lock:
        print(f"[{time.strftime('%H:%M:%S')}] {user}: {msg}", flush=True)


def clamp(x, lo=0.05, hi=0.97):
    return max(lo, min(hi, x))


def ok(status, data, what):
    if status >= 400:
        raise RuntimeError(f"{what}: HTTP {status} {str(data)[:300]}")
    return data


# ---------------- testlar ----------------
def take_quiz(tok, quiz_id, skill, rnd, user):
    s, d = call("POST", f"quizzes/{quiz_id}/start/", tok)
    if s == 409:
        log(user, f"test {quiz_id} avval topshirilgan"); return
    d = ok(s, d, "start")
    answers = {}
    for q in d["questions"]:
        ids = [c["id"] for c in q["choices"]]
        key = KEYS.get(q["id"])
        if q["kind"] == "likert" or key is None:
            # so'rovnoma: o'rta-yuqori qiymatlarga moyil
            answers[str(q["id"])] = [rnd.choices(ids, weights=[1, 2, 3, 4, 3][: len(ids)] or None)[0]]
        elif rnd.random() < skill:
            answers[str(q["id"])] = list(key)
        else:
            wrong = [i for i in ids if i not in key] or ids
            if q["kind"] == "multiple" and len(key) > 1:
                answers[str(q["id"])] = key[:-1] + [rnd.choice(wrong)]
            else:
                answers[str(q["id"])] = [rnd.choice(wrong)]
    s, d = call("POST", f"quizzes/{quiz_id}/submit/", tok, {"answers": answers})
    d = ok(s, d, "submit")
    log(user, f"test {quiz_id} topshirildi: {d.get('percent', d.get('score'))}")


# ---------------- ER ----------------
def reference(lab_id):
    return REF[lab_id]


def target_diagram(ref, skill, rnd):
    ents = [e for e in ref["entities"] if rnd.random() < clamp(skill + 0.3)]
    if len(ents) < 2:
        ents = ref["entities"][:2]
    out_e = []
    for e in ents:
        e = copy.deepcopy(e)
        attrs = []
        for a in e["attributes"]:
            if rnd.random() < clamp(skill + 0.25):
                if a["key"] == "pk" and rnd.random() < (1 - skill) * 0.5:
                    a = {**a, "key": ""}
                attrs.append(a)
        e["attributes"] = attrs or e["attributes"][:1]
        out_e.append(e)
    kept = {e["id"] for e in out_e}
    rels = []
    for r in ref["relationships"]:
        if r["source"] in kept and r["target"] in kept and rnd.random() < clamp(skill + 0.2):
            r = copy.deepcopy(r)
            if rnd.random() < (1 - skill) * 0.6:
                r["source_card"], r["target_card"] = r["target_card"], r["source_card"]
                if r["source_card"] == r["target_card"]:
                    r["target_card"] = "1" if r["target_card"] == "N" else "N"
            rels.append(r)
    return out_e, rels


def states(ents, rels, strategy, rnd):
    """Bo'sh holatdan yakuniy diagrammagacha oraliq holatlar ketma-ketligi."""
    cur_e, cur_r, seq = [], [], []
    snap = lambda: seq.append({"entities": copy.deepcopy(cur_e), "relationships": copy.deepcopy(cur_r)})
    if strategy == "objects_first":
        for e in ents:
            cur_e.append(e); snap()
        for r in rels:
            cur_r.append(r); snap()
    else:
        pending = list(rels)
        for e in ents:
            cur_e.append(e); snap()
            ids = {x["id"] for x in cur_e}
            for r in [r for r in pending if r["source"] in ids and r["target"] in ids]:
                cur_r.append(r); pending.remove(r); snap()
            if strategy == "trial" and rnd.random() < 0.7:
                junk = {"id": f"tmp{len(seq)}", "name": f"Qoralama{len(seq)}", "x": 700, "y": 40 * len(seq),
                        "attributes": [{"key": "pk", "name": "id"}]}
                cur_e.append(junk); snap(); cur_e.remove(junk); snap()
    return seq


def do_er(tok, lab_id, skill, strategy, rnd, user):
    ents, rels = target_diagram(reference(lab_id), skill, rnd)
    seq = states(ents, rels, strategy, rnd)
    checks = 6 if strategy == "trial" else rnd.choice([1, 2])
    check_at = set(rnd.sample(range(len(seq)), min(checks, len(seq))))
    for i, diagram in enumerate(seq):
        ok(*call("POST", f"labs/{lab_id}/er-snapshot/", tok, {"diagram": diagram}), "er-snapshot")
        if i in check_at:
            ok(*call("POST", f"labs/{lab_id}/run/", tok, {"diagram": diagram, "confidence": rnd.randint(2, 5)}), "run")
        time.sleep(3.2)  # er_snapshot: 20/min
    s, d = call("POST", f"labs/{lab_id}/submit/", tok, {"diagram": seq[-1], "confidence": rnd.randint(2, 5)})
    d = ok(s, d, "submit")
    g = d.get("grade", {})
    log(user, f"ER lab {lab_id} ({strategy}): ball {g.get('score')}, manba {g.get('source')}, tuzatilgan ko'rsatildi: {bool(d.get('fix'))}")


# ---------------- talaba ----------------
def student(username, password, group, index, seed):
    rnd = random.Random(seed)
    pre = PRE_SKILL[group][index]
    post = clamp(pre + 0.20 * (1 - pre) + rnd.gauss(0, 0.07))       # bir xil qoida, ikkala guruh
    delayed = clamp(post - 0.05 + rnd.gauss(0, 0.06))
    strategy = STRATEGIES[index]
    try:
        time.sleep(index * 2)
        tok = login(username, password)
        log(username, f"kirdi ({group}); daraja: kirish {pre:.2f}, chiqish {post:.2f}, kechiktirilgan {delayed:.2f}")
        ok(*call("POST", "auth/consent/", tok, {"agreed": True}), "consent")
        take_quiz(tok, QUIZ["pre"], pre, rnd, username)
        do_er(tok, LABS["kirish"], pre, strategy, rnd, username)
        take_quiz(tok, QUIZ["post"], post, rnd, username)
        do_er(tok, LABS["chiqish"], post, strategy if rnd.random() < 0.6 else rnd.choice(STRATEGIES), rnd, username)
        take_quiz(tok, QUIZ["delayed"], delayed, rnd, username)
        do_er(tok, LABS["kechiktirilgan"], delayed, strategy, rnd, username)
        s, d = call("GET", "quizzes/", tok)
        d = d.get("results", d) if isinstance(d, dict) else d
        for q in d:
            if q["kind"] == "survey":
                take_quiz(tok, q["id"], 0.5, rnd, username)
        log(username, "TAYYOR")
    except Exception as exc:  # noqa: BLE001
        log(username, f"XATO: {exc}")
