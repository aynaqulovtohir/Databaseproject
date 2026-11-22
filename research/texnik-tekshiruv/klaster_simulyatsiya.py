"""Klaster (akademik guruh) ta'siri bilan takroriy simulyatsiya: platformaning o'z statistik funksiyalari
(backend/competence/stats.py) guruh ta'siri bor ma'lumotlarda.

Generator takroriy_simulyatsiya.py bilan bir xil (a0 ~ U(0.20, 0.80); a1 = a0 + 0.20·(1 − a0) + N(0, 0.07²);
20 savolli test), bunga qo'shimcha ravishda har bir akademik guruhga chiqish testida umumiy siljish u_g ~ N(0, σ_u²)
qo'shiladi (randomizatsiyadan keyingi guruh ta'siri: bir o'qituvchi, bir mashg'ulot). σ_u maqsadli ICC ga
(chiqish testining kirish testi hisobga olingandan keyingi qoldig'i bo'yicha) katta namunada kalibrlanadi.

Ikki dizayn:
  A — klasterli: AI guruh bo'yicha yoqiladi, har bir shartda 2 ta guruh (platformadagi pilot rejasi);
  B — guruh ichida taqsimlash: 4 ta guruhning har biri ikkita platforma guruhiga bo'linadi (yarmi AI, yarmi nazorat),
      shuning uchun guruh ta'siri ikkala shartga teng tushadi.

Ishlatish (shu papkada):
  python3 -I klaster_simulyatsiya.py ../../backend/competence/stats.py natijalar/klaster_simulyatsiya.json
"""
import importlib.util
import json
import math
import random
import sys
import time

spec = importlib.util.spec_from_file_location("platform_stats", sys.argv[1])
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

ITEMS = 20
R = 2000
SEED = 20261123
ALPHA = S.ALPHA
CLUSTERS = 4          # akademik guruhlar soni (pilotdagi kabi)
ICC_WARN = 0.05       # platforma ogohlantiradigan chegara (experiment.py: «ICC 0.05 dan katta bo'lsa ...»)


def clamp(x):
    return min(1.0, max(0.0, x))


def score(rnd, ability):
    return 100.0 * sum(rnd.random() < ability for _ in range(ITEMS)) / ITEMS


def student(rnd, delta, shift):
    a0 = rnd.uniform(0.20, 0.80)
    a1 = clamp(a0 + 0.20 * (1 - a0) + rnd.gauss(0, 0.07) + delta)
    return score(rnd, a0), score(rnd, a1) + shift


def residual_sd(rnd, n=40000):
    """Chiqish testining kirish testi bo'yicha regressiya qoldig'i SD si (guruh ta'sirisiz)."""
    pairs = [student(rnd, 0.0, 0.0) for _ in range(n)]
    xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
    mx, my = sum(xs) / n, sum(ys) / n
    b = sum((x - mx) * (y - my) for x, y in pairs) / sum((x - mx) ** 2 for x in xs)
    res = [y - my - b * (x - mx) for x, y in pairs]
    return math.sqrt(sum(r * r for r in res) / (n - 2))


def wilson(k, n, z=1.959964):
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / den
    return [round(centre - half, 4), round(centre + half, 4)]


def rate(flags):
    k = sum(flags)
    return {"k": k, "n": len(flags), "rate": round(k / len(flags), 4), "ci95": wilson(k, len(flags))}


def trial(rnd, n, delta, sigma_u, design):
    """n — har bir shartdagi talabalar soni. Qaytaradi: ANCOVA rad etdimi, platformaning ICC bahosi."""
    shifts = [rnd.gauss(0, sigma_u) for _ in range(CLUSTERS)]
    exp, con = [], []   # (pre, post, guruh)
    if design == "A":   # 0,1 — AI; 2,3 — nazorat
        for g in range(CLUSTERS):
            size = n // 2 + (1 if g % 2 == 0 and n % 2 else 0)
            for _ in range(size):
                arm = exp if g < 2 else con
                pre, post = student(rnd, delta if g < 2 else 0.0, shifts[g])
                arm.append((pre, post, g))
    else:               # har bir guruhda yarmi AI, yarmi nazorat
        for i in range(2 * n):
            g = i % CLUSTERS
            in_exp = i < n  # birinchi n ta talaba guruhlar bo'ylab navbat bilan AI ga, keyingi n tasi nazoratga
            arm = exp if in_exp else con
            pre, post = student(rnd, delta if in_exp else 0.0, shifts[g])
            arm.append((pre, post, g))
    anc = S.ancova({"experimental": [(a, b) for a, b, _ in exp], "control": [(a, b) for a, b, _ in con]})
    icc = None
    if anc:
        b0, b1, b2 = anc["beta"]
        by_group = {}
        for flag, rows in ((1.0, exp), (0.0, con)):
            for a, b, g in rows:
                key = (g, flag) if design == "B" else g
                by_group.setdefault(key, []).append(b - (b0 + b1 * flag + b2 * a))
        res = S.icc_oneway(list(by_group.values()))
        icc = res["icc"] if res else None
    return {"reject": anc is not None and anc["p"] < ALPHA, "icc": icc}


rnd = random.Random(SEED)
t0 = time.time()
sd_e = residual_sd(random.Random(SEED + 7))
out = {"R": R, "seed": SEED, "alpha": ALPHA, "clusters": CLUSTERS, "residual_sd": round(sd_e, 3),
       "icc_warning_threshold": ICC_WARN, "rows": []}
for icc_true in (0.0, 0.05, 0.10):
    sigma_u = math.sqrt(icc_true / (1 - icc_true)) * sd_e
    for design in ("A", "B"):
        for n in (10, 20, 64):
            for delta in (0.0, 0.10):
                rows = [trial(rnd, n, delta, sigma_u, design) for _ in range(R)]
                iccs = [r["icc"] for r in rows if r["icc"] is not None]
                row = {
                    "icc_true": icc_true, "sigma_u_points": round(sigma_u, 2), "design": design, "n_per_arm": n,
                    "delta": delta, "ancova_reject": rate([r["reject"] for r in rows]),
                    "icc_mean": round(sum(iccs) / len(iccs), 4) if iccs else None,
                    "icc_warning": rate([r["icc"] is not None and r["icc"] > ICC_WARN for r in rows]),
                }
                out["rows"].append(row)
                print(icc_true, design, n, delta, row["ancova_reject"]["rate"], row["icc_mean"],
                      row["icc_warning"]["rate"], round(time.time() - t0), flush=True)
json.dump(out, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)
print("residual_sd", round(sd_e, 3), "vaqt", round(time.time() - t0, 1))
