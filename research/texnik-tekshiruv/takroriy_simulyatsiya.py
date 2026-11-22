"""Monte Karlo: platformaning o'z statistik funksiyalari (backend/competence/stats.py) sintetik generator qoidasi
bilan yaratilgan ko'p sonli ma'lumot to'plamlarida.

Generator (research/texnik-tekshiruv/sintetik.py bilan bir xil qoida):
  a0 ~ U(0.20, 0.80); a1 = a0 + 0.20·(1 − a0) + N(0, 0.07²) [+ δ tajriba guruhida]; kechiktirilgan a2 = a1 + N(0, 0.07²)
  test: 20 savol, har biri a ehtimol bilan to'g'ri → ball = 100·to'g'ri/20
Ishlatish (shu papkada): python3 -I takroriy_simulyatsiya.py ../../backend/competence/stats.py natijalar/takroriy_simulyatsiya.json
"""
import importlib.util
import json
import random
import sys
import time

spec = importlib.util.spec_from_file_location("platform_stats", sys.argv[1])
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

ITEMS = 20
R = 2000
SEED = 20261122
ALPHA = S.ALPHA


def clamp(x):
    return min(1.0, max(0.0, x))


def score(rnd, ability):
    return 100.0 * sum(rnd.random() < ability for _ in range(ITEMS)) / ITEMS


def student(rnd, delta):
    a0 = rnd.uniform(0.20, 0.80)
    a1 = clamp(a0 + 0.20 * (1 - a0) + rnd.gauss(0, 0.07) + delta)
    a2 = clamp(a1 + rnd.gauss(0, 0.07))
    return score(rnd, a0), score(rnd, a1), score(rnd, a2)


def gain(pre, post):
    return (post - pre) / (100 - pre) if pre < 100 else None


def trial(rnd, n, delta):
    """Bitta tajriba: har bir shartda n talaba (2 ta akademik guruhga bo'lingan). Platforma tahlil zanjiri."""
    exp = [student(rnd, delta) for _ in range(n)]
    con = [student(rnd, 0.0) for _ in range(n)]
    anc = S.ancova({"experimental": [(a, b) for a, b, _ in exp], "control": [(a, b) for a, b, _ in con]})
    sec = [
        S.student_t_test([b for _, b, _ in exp], [b for _, b, _ in con]),
        S.mann_whitney([g for g in (gain(a, b) for a, b, _ in exp) if g is not None],
                       [g for g in (gain(a, b) for a, b, _ in con) if g is not None]),
        S.student_t_test([c for _, _, c in exp], [c for _, _, c in con]),
    ]
    ps = [t["p"] if t else None for t in sec]
    holm = S.holm(ps)
    # ICC: ANCOVA qoldiqlari 4 ta akademik guruh bo'yicha (klaster ta'siri dasturlanmagan)
    icc = None
    if anc:
        b0, b1, b2 = anc["beta"]
        half = n // 2
        clusters = [
            [b - (b0 + b1 + b2 * a) for a, b, _ in exp[:half]], [b - (b0 + b1 + b2 * a) for a, b, _ in exp[half:]],
            [b - (b0 + b2 * a) for a, b, _ in con[:half]], [b - (b0 + b2 * a) for a, b, _ in con[half:]],
        ]
        icc = S.icc_oneway(clusters)
    return {
        "ancova_sig": anc is not None and anc["p"] < ALPHA,
        "ancova_ok": anc is not None,
        "ci_covers_delta0": anc is not None and anc["adjusted_diff_ci"][0] <= 0 <= anc["adjusted_diff_ci"][1],
        "raw_any_sig": any(p is not None and p < ALPHA for p in ps),
        "holm_any_sig": any(p is not None and p < ALPHA for p in holm),
        "icc_pos": icc is not None and icc["icc"] > 0,
        "icc": icc["icc"] if icc else None,
        "post_d": S.welch_t_test([b for _, b, _ in exp], [b for _, b, _ in con]),
    }


def competence_overall(rnd, n):
    """Kompetentlikdagi «Umumiy» o'sish: eski usul (kesimlarda turli komponentlar) va yangi usul (umumiy komponentlar).

    Kognitiv = test bali (boshida va oxirida); amaliy-loyihaviy faqat oxirida, S1 da kuzatilgan taqsimotga yaqin:
    N(13; 13²), [0; 100] oralig'ida. Haqiqiy kognitiv o'zgarish — generator qoidasi bo'yicha o'sish (musbat).
    """
    pre, post, practical = [], [], []
    for _ in range(n):
        a, b, _ = student(rnd, 0.0)
        pre.append(a); post.append(b); practical.append(min(100.0, max(0.0, rnd.gauss(13, 13))))
    old = S.paired_t_test(pre, [(b + p) / 2 for b, p in zip(post, practical)])
    new = S.paired_t_test(pre, post)
    return {
        "old_sig_decline": old is not None and old["p"] < ALPHA and old["mean_diff"] < 0,
        "new_sig_decline": new is not None and new["p"] < ALPHA and new["mean_diff"] < 0,
        "new_sig_growth": new is not None and new["p"] < ALPHA and new["mean_diff"] > 0,
    }


def wilson(k, n, z=1.959964):
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / den
    return [round(centre - half, 4), round(centre + half, 4)]


def rate(rows, key):
    k = sum(1 for r in rows if r[key])
    return {"k": k, "n": len(rows), "rate": round(k / len(rows), 4), "ci95": wilson(k, len(rows))}


rnd = random.Random(SEED)
out = {"R": R, "seed": SEED, "items": ITEMS, "alpha": ALPHA, "trials": [], "competence": []}
t0 = time.time()
for n in (10, 20, 64):
    for delta in (0.0, 0.05, 0.10, 0.15):
        rows = [trial(rnd, n, delta) for _ in range(R)]
        ds = [r["post_d"]["cohens_d"] for r in rows if r["post_d"] and r["post_d"].get("cohens_d") is not None] if rows[0]["post_d"] and "cohens_d" in rows[0]["post_d"] else []
        iccs = [r["icc"] for r in rows if r["icc"] is not None]
        out["trials"].append({
            "n_per_arm": n, "delta": delta,
            "ancova_reject": rate(rows, "ancova_sig"),
            "ancova_computed": rate(rows, "ancova_ok"),
            "ci_covers_zero": rate(rows, "ci_covers_delta0"),
            "secondary_any_raw": rate(rows, "raw_any_sig"),
            "secondary_any_holm": rate(rows, "holm_any_sig"),
            "icc_positive": rate(rows, "icc_pos"),
            "icc_mean": round(sum(iccs) / len(iccs), 4) if iccs else None,
        })
        print(n, delta, out["trials"][-1]["ancova_reject"], round(time.time() - t0, 1), flush=True)
for n in (10, 20, 64):
    rows = [competence_overall(rnd, n) for _ in range(R)]
    out["competence"].append({"n_per_arm": n, "old_sig_decline": rate(rows, "old_sig_decline"),
                              "new_sig_decline": rate(rows, "new_sig_decline"), "new_sig_growth": rate(rows, "new_sig_growth")})
    print("komp", n, out["competence"][-1], flush=True)

# Kuzatilgan effekt hajmi (post test, δ → d) — tavsif uchun: katta namunada
big = random.Random(SEED + 1)
for delta in (0.05, 0.10, 0.15):
    e = [student(big, delta)[1] for _ in range(20000)]
    c = [student(big, 0.0)[1] for _ in range(20000)]
    me, mc = sum(e) / len(e), sum(c) / len(c)
    sd = ((sum((x - me) ** 2 for x in e) + sum((x - mc) ** 2 for x in c)) / (len(e) + len(c) - 2)) ** 0.5
    out.setdefault("delta_to_d", {})[str(delta)] = round((me - mc) / sd, 3)
json.dump(out, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)
print("delta->d", out["delta_to_d"], "vaqt", round(time.time() - t0, 1))
