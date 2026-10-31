"""Tajriba samaradorligi uchun statistik mezonlar (toza Python, tashqi kutubxonasiz).

- Pirson χ² (darajalar taqsimoti: tajriba va nazorat guruhlari), Kramer V — effekt hajmi;
- Styudent t-testi (Uelch varianti: dispersiyalar teng bo'lishi shart emas), Koen d va Xedjes g;
- Mann–Uitni U testi (normal yaqinlashish, bir xil qiymatlar tuzatmasi bilan) — taqsimot normal bo'lmasa;
- Kraskel–Uollis H testi — uch va undan ko'p guruh (masalan, loyihalash strategiyalari) parametrsiz;
- juftlangan t-test — bitta guruhning tajriba boshi va oxiri (o'sish);
- Xolm tuzatishi — bir nechta ikkilamchi solishtiruvda I tur xatoni nazorat qilish;
- sinfichi korrelyatsiya ICC(1) va dizayn effekti — talabalar guruhlarga (klasterlarga) bo'lingan tajriba uchun;
- TOST — ikki o'rtachaning ekvivalentligi (masalan, testning parallel variantlari);
- Spirmen rang korrelyatsiyasi (Fisher z ishonch oralig'i bilan);
- ishonch oraliqlari: o'rtachalar farqi (Styudent, Uelch), Xodjes–Leman siljishi, Xedjes g, ANCOVA tuzatilgan farqi.

p-qiymatlar uchun to'liq bo'lmagan gamma va beta funksiyalari (Numerical Recipes, 6.2 va 6.4) ishlatiladi.
Natijalar scipy.stats bilan solishtirib tekshirilgan (tests.py dagi namunaviy qiymatlar).
"""
import math

ALPHA = 0.05
MIN_EXPECTED = 5  # χ² ishonchli bo'lishi uchun har bir katakdagi kutilgan son (Kochran qoidasi)
_EPS = 3e-14
_MAX_ITER = 300


def _gamma_series(a, x):
    total = term = 1 / a
    n = a
    for _ in range(_MAX_ITER):
        n += 1
        term *= x / n
        total += term
        if abs(term) < abs(total) * _EPS:
            break
    return total * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gamma_fraction(a, x):
    b = x + 1 - a
    c = 1 / 1e-300
    d = 1 / b
    h = d
    for i in range(1, _MAX_ITER):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < _EPS:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def gamma_q(a, x):
    """Yuqori regulyarlangan to'liq bo'lmagan gamma funksiya Q(a, x)."""
    if x <= 0:
        return 1.0
    if x < a + 1:
        return 1 - _gamma_series(a, x)
    return _gamma_fraction(a, x)


def chi2_sf(x, df):
    return gamma_q(df / 2, x / 2)


def _beta_fraction(a, b, x):
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1e-300 if abs(d) < 1e-300 else d
    d = 1 / d
    h = d
    for m in range(1, _MAX_ITER):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1e-300 if abs(d) < 1e-300 else d
        c = 1 + aa / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1e-300 if abs(d) < 1e-300 else d
        c = 1 + aa / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < _EPS:
            break
    return h


def beta_i(a, b, x):
    """Regulyarlangan to'liq bo'lmagan beta funksiya I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _beta_fraction(a, b, x) / a
    return 1 - front * _beta_fraction(b, a, 1 - x) / b


def t_two_sided_p(t, df):
    return beta_i(df / 2, 0.5, df / (df + t * t))


def normal_two_sided_p(z):
    return math.erfc(abs(z) / math.sqrt(2))


def _mean(values):
    return sum(values) / len(values)


def _variance(values):
    mean = _mean(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def describe(values):
    """n, o'rtacha va standart chetlanish (n − 1)."""
    if not values:
        return {"n": 0, "mean": None, "sd": None}
    return {"n": len(values), "mean": _mean(values), "sd": math.sqrt(_variance(values)) if len(values) > 1 else None}


def chi_square(table):
    """Pirson χ² mustaqillik testi. table — qatorlar (guruhlar) × ustunlar (darajalar), sonlar.

    Hamma nol ustun (hech kim shu darajada emas) tashlab yuboriladi. Ikkita qator va ikkita ustun
    bo'lmasa, test qo'llanmaydi (None).
    """
    columns = [index for index in range(len(table[0])) if any(row[index] for row in table)]
    rows = [[row[index] for index in columns] for row in table if sum(row)]
    if len(rows) < 2 or len(columns) < 2:
        return None
    total = sum(map(sum, rows))
    row_sums = [sum(row) for row in rows]
    column_sums = [sum(row[index] for row in rows) for index in range(len(columns))]
    chi2 = 0.0
    min_expected = math.inf
    for i, row in enumerate(rows):
        for j, observed in enumerate(row):
            expected = row_sums[i] * column_sums[j] / total
            min_expected = min(min_expected, expected)
            chi2 += (observed - expected) ** 2 / expected
    df = (len(rows) - 1) * (len(columns) - 1)
    return {
        "chi2": chi2,
        "df": df,
        "p": chi2_sf(chi2, df),
        "cramers_v": math.sqrt(chi2 / (total * (min(len(rows), len(columns)) - 1))),
        "min_expected": min_expected,
        "reliable": min_expected >= MIN_EXPECTED,
    }


def fisher_exact(table):
    """Fisherning aniq testi, 2 × 2 jadval, ikki tomonlama: kuzatilganidan ehtimolligi katta bo'lmagan barcha
    jadvallar (chegaralar saqlangan holda) ehtimolliklari yig'indisi (scipy.stats.fisher_exact bilan bir xil).

    χ² ning kutilgan sonlari kichik bo'lganda (MIN_EXPECTED dan kam) ishlatiladi. Bo'sh qator yoki ustun — None.
    """
    (a, b), (c, d) = table
    row1, col1, total = a + b, a + c, a + b + c + d
    if not row1 or not c + d or not col1 or not b + d:
        return None

    def log_p(x):
        return (
            math.lgamma(row1 + 1) - math.lgamma(x + 1) - math.lgamma(row1 - x + 1)
            + math.lgamma(total - row1 + 1) - math.lgamma(col1 - x + 1) - math.lgamma(total - row1 - col1 + x + 1)
            - math.lgamma(total + 1) + math.lgamma(col1 + 1) + math.lgamma(total - col1 + 1)
        )

    observed = log_p(a)
    support = range(max(0, row1 + col1 - total), min(row1, col1) + 1)
    p = sum(math.exp(log_p(x)) for x in support if log_p(x) <= observed + 1e-7)
    return {"p": min(1.0, p)}


def welch_t_test(a, b):
    """Ikki mustaqil tanlanma: Uelch t-testi va effekt hajmi (Koen d, Xedjes g; birlashgan dispersiya bilan)."""
    if len(a) < 2 or len(b) < 2:
        return None
    var_a, var_b = _variance(a), _variance(b)
    se2 = var_a / len(a) + var_b / len(b)
    pooled = math.sqrt(((len(a) - 1) * var_a + (len(b) - 1) * var_b) / (len(a) + len(b) - 2))
    diff = _mean(a) - _mean(b)
    if se2 == 0:
        return None
    t = diff / math.sqrt(se2)
    df = se2**2 / ((var_a / len(a)) ** 2 / (len(a) - 1) + (var_b / len(b)) ** 2 / (len(b) - 1))
    d = diff / pooled if pooled else None
    correction = _hedges_correction(len(a) + len(b))
    return {"t": t, "df": df, "p": t_two_sided_p(t, df), "cohens_d": d, "hedges_g": d * correction if d is not None else None}


def _pooled_sd(a, b):
    return math.sqrt(((len(a) - 1) * _variance(a) + (len(b) - 1) * _variance(b)) / (len(a) + len(b) - 2))


def _hedges_correction(n):
    return 1 - 3 / (4 * n - 9)


def mean_difference_ci(a, b, equal_var, alpha=ALPHA):
    """O'rtachalar farqi (a − b) va (1 − α) ishonch oralig'i: Styudent (equal_var) yoki Uelch shaklida —
    tanlangan t-test bilan mos: oraliq 0 ni o'z ichiga olmasa, test ham p < α beradi."""
    if len(a) < 2 or len(b) < 2:
        return None
    if equal_var:
        df = len(a) + len(b) - 2
        se2 = _pooled_sd(a, b) ** 2 * (1 / len(a) + 1 / len(b))
    else:
        var_a, var_b = _variance(a) / len(a), _variance(b) / len(b)
        se2 = var_a + var_b
        df = se2**2 / (var_a**2 / (len(a) - 1) + var_b**2 / (len(b) - 1)) if se2 else 0
    if se2 == 0:
        return None
    diff = _mean(a) - _mean(b)
    half = _t_ppf(1 - alpha / 2, df) * math.sqrt(se2)
    return {"diff": diff, "ci": (diff - half, diff + half)}


def hedges_g_ci(a, b, alpha=ALPHA):
    """Xedjes g va taxminiy (1 − α) ishonch oralig'i: Var(g) ≈ (n₁ + n₂) / (n₁n₂) + g² / (2(n₁ + n₂)) (Xedjes, Olkin, 1985)."""
    if len(a) < 2 or len(b) < 2:
        return None
    pooled = _pooled_sd(a, b)
    if not pooled:
        return None
    n1, n2 = len(a), len(b)
    g = (_mean(a) - _mean(b)) / pooled * _hedges_correction(n1 + n2)
    half = normal_ppf(1 - alpha / 2) * math.sqrt((n1 + n2) / (n1 * n2) + g * g / (2 * (n1 + n2)))
    return {"value": g, "ci": (g - half, g + half)}


def hodges_lehmann(a, b, alpha=ALPHA):
    """Xodjes–Leman siljishi (a − b): barcha juft farqlar medianasi — Mann–Uitni testiga mos baho (parametrsiz).

    Ishonch oralig'i — Mozes usuli: mann_whitney testini teskari yechish (a − δ va b testda rad etilmaydigan δ lar),
    uchlari ochiq; bir xil ballar ko'p bo'lsa, uchi aynan 0 ga tushib, test ahamiyatli chiqishi mumkin. Tanlanma juda
    kichik bo'lsa, (1 − α) oraliqqa erishib bo'lmaydi: ci = None.
    """
    n1, n2 = len(a), len(b)
    if not n1 or not n2:
        return None
    diffs = sorted(x - y for x in a for y in b)
    total = len(diffs)
    middle = total // 2
    shift = diffs[middle] if total % 2 else (diffs[middle - 1] + diffs[middle]) / 2
    # Chegaralar juft farqlar orasida izlanadi: u yerda guruhlararo teng qiymatlar yo'q, faqat guruh ichidagilari qoladi
    ties = _ranks(a)[1] + _ranks(b)[1]
    variance = _mann_whitney_variance(n1, n2, ties)
    if variance <= 0:
        return None
    k = math.floor(total / 2 - normal_ppf(1 - alpha / 2) * math.sqrt(variance))
    ci = (diffs[k], diffs[total - 1 - k]) if k >= 0 else None
    return {"shift": shift, "ci": ci, "approximate": min(n1, n2) < 8}


def _ranks(values):
    """O'rtacha ranglar (bir xil qiymatlarga o'rtacha rang) va bir xil qiymatlar guruhlari o'lchamlari."""
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    ties = []
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        ties.append(j - i + 1)
        i = j + 1
    return ranks, ties


def _mann_whitney_variance(n1, n2, ties):
    n = n1 + n2
    return n1 * n2 / 12 * ((n + 1) - sum(t**3 - t for t in ties) / (n * (n - 1)))


def mann_whitney(a, b):
    """Mann–Uitni U testi: normal yaqinlashish, bir xil qiymatlar tuzatmasi, uzluksizlik tuzatmasisiz.

    U — birinchi tanlanma uchun. Kichik tanlanmalarda (har birida 8 dan kam) yaqinlashish taxminiy.
    """
    n1, n2 = len(a), len(b)
    if not n1 or not n2:
        return None
    ranks, ties = _ranks(list(a) + list(b))
    u = sum(ranks[:n1]) - n1 * (n1 + 1) / 2
    n = n1 + n2
    variance = _mann_whitney_variance(n1, n2, ties)
    if variance <= 0:
        return None
    z = (u - n1 * n2 / 2) / math.sqrt(variance)
    return {"u": u, "z": z, "p": normal_two_sided_p(z), "approximate": min(n1, n2) < 8}


def kruskal_wallis(samples):
    """Kraskel–Uollis H testi (uch va undan ko'p mustaqil guruh, parametrsiz), bir xil qiymatlar tuzatmasi bilan.

    Bo'sh guruhlar tashlab yuboriladi; ikkitadan kam guruh qolsa — None. Effekt hajmi: ε² = H / (n − 1).
    """
    samples = [list(sample) for sample in samples if sample]
    values = [value for sample in samples for value in sample]
    n = len(values)
    if len(samples) < 2 or n < 3:
        return None
    ranks, ties = _ranks(values)
    total, start = 0.0, 0
    for sample in samples:
        total += sum(ranks[start:start + len(sample)]) ** 2 / len(sample)
        start += len(sample)
    correction = 1 - sum(t**3 - t for t in ties) / (n**3 - n)
    if correction <= 0:
        return None
    h = (12 / (n * (n + 1)) * total - 3 * (n + 1)) / correction
    df = len(samples) - 1
    return {"h": h, "df": df, "p": chi2_sf(h, df), "epsilon2": h / (n - 1)}


def linear_residuals(x, y):
    """y ning x ga chiziqli regressiyasi qoldiqlari. x o'zgarmas bo'lsa — o'rtachadan farqlar."""
    mean_x, mean_y = _mean(x), _mean(y)
    sxx = sum((value - mean_x) ** 2 for value in x)
    slope = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y)) / sxx if sxx else 0.0
    return [b - mean_y - slope * (a - mean_x) for a, b in zip(x, y)]


def spearman(x, y, alpha=ALPHA):
    """Spirmen ρ: ranglar bo'yicha Pirson r (bir xil qiymatlarga o'rtacha rang), p — t yaqinlashishi (df = n − 2),
    (1 − α) ishonch oralig'i — Fisher z, Bonett–Rayt xatosi √((1 + ρ²/2) / (n − 3)). Qiymatlardan biri o'zgarmas — None."""
    n = len(x)
    if n < 3:
        return None
    rx, ry = _ranks(list(x))[0], _ranks(list(y))[0]
    mean_x, mean_y = _mean(rx), _mean(ry)
    sxx = sum((value - mean_x) ** 2 for value in rx)
    syy = sum((value - mean_y) ** 2 for value in ry)
    if not sxx or not syy:
        return None
    rho = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry)) / math.sqrt(sxx * syy)
    rho = max(-1.0, min(1.0, rho))
    if abs(rho) == 1:
        return {"n": n, "rho": rho, "p": 0.0, "ci": None}
    t = rho * math.sqrt((n - 2) / (1 - rho * rho))
    ci = None
    if n > 3:
        z, half = math.atanh(rho), normal_ppf(1 - alpha / 2) * math.sqrt((1 + rho * rho / 2) / (n - 3))
        ci = (math.tanh(z - half), math.tanh(z + half))
    return {"n": n, "rho": rho, "p": t_two_sided_p(t, n - 2), "ci": ci}


def paired_t_test(before, after):
    """Juftlangan t-test (bir talabaning ikki o'lchovi) va effekt hajmi d_z = o'rtacha farq / farqlar sd."""
    diffs = [y - x for x, y in zip(before, after)]
    if len(diffs) < 2:
        return None
    sd = math.sqrt(_variance(diffs))
    mean = _mean(diffs)
    if sd == 0:
        return None
    t = mean / (sd / math.sqrt(len(diffs)))
    df = len(diffs) - 1
    return {"n": len(diffs), "mean_diff": mean, "t": t, "df": df, "p": t_two_sided_p(t, df), "d_z": mean / sd}


# ---------- Shartlarni tekshirish, ANCOVA va statistik quvvat ----------


def normal_cdf(z):
    return 0.5 * math.erfc(-z / math.sqrt(2))


_ACKLAM_A = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02, 1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00)
_ACKLAM_B = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02, 6.680131188771972e01, -1.328068155288572e01)
_ACKLAM_C = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00, -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00)
_ACKLAM_D = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00)


def normal_ppf(p):
    """Standart normal taqsimot kvantili (Acklam yaqinlashishi + bitta Galley aniqlashtirishi)."""
    if not 0 < p < 1:
        raise ValueError("p 0 va 1 orasida bo'lishi kerak")
    a, b, c, d = _ACKLAM_A, _ACKLAM_B, _ACKLAM_C, _ACKLAM_D
    low = 0.02425
    if p < low:
        q = math.sqrt(-2 * math.log(p))
        x = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    elif p <= 1 - low:
        q = p - 0.5
        r = q * q
        x = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (
            ((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1
        )
    else:
        q = math.sqrt(-2 * math.log(1 - p))
        x = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    error = normal_cdf(x) - p
    u = error * math.sqrt(2 * math.pi) * math.exp(x * x / 2)
    return x - u / (1 + x * u / 2)


def f_sf(f, df1, df2):
    """F-taqsimotning o'ng dumi P(F > f)."""
    if f <= 0:
        return 1.0
    return beta_i(df2 / 2, df1 / 2, df2 / (df2 + df1 * f))


def shapiro_wilk(values):
    """Shapiro–Uilk normallik testi (Royston, 1995, AS R94): 3 ≤ n ≤ 5000. p < 0.05 — taqsimot normal emas."""
    x = sorted(values)
    n = len(x)
    if n < 3 or n > 5000 or x[-1] - x[0] <= 0:
        return None
    m = [normal_ppf((i - 0.375) / (n + 0.25)) for i in range(1, n + 1)]
    mm = sum(value * value for value in m)
    u = 1 / math.sqrt(n)
    if n == 3:
        a = [-math.sqrt(0.5), 0.0, math.sqrt(0.5)]
    else:
        c = [value / math.sqrt(mm) for value in m]
        an = c[-1] + 0.221157 * u - 0.147981 * u**2 - 2.071190 * u**3 + 4.434685 * u**4 - 2.706056 * u**5
        if n > 5:
            an1 = c[-2] + 0.042981 * u - 0.293762 * u**2 - 1.752461 * u**3 + 5.682633 * u**4 - 3.582633 * u**5
            phi = (mm - 2 * m[-1] ** 2 - 2 * m[-2] ** 2) / (1 - 2 * an**2 - 2 * an1**2)
            a = [value / math.sqrt(phi) for value in m]
            a[0], a[1], a[-2], a[-1] = -an, -an1, an1, an
        else:
            phi = (mm - 2 * m[-1] ** 2) / (1 - 2 * an**2)
            a = [value / math.sqrt(phi) for value in m]
            a[0], a[-1] = -an, an
    mean = sum(x) / n
    w = sum(ai * xi for ai, xi in zip(a, x)) ** 2 / sum((xi - mean) ** 2 for xi in x)
    w = min(w, 1.0)
    if n == 3:
        p = max(0.0, min(1.0, 6 / math.pi * (math.asin(math.sqrt(w)) - math.asin(math.sqrt(0.75)))))
        return {"w": w, "p": p}
    if n <= 11:
        gamma = -2.273 + 0.459 * n
        mu = 0.5440 - 0.39978 * n + 0.025054 * n**2 - 0.0006714 * n**3
        sigma = math.exp(1.3822 - 0.77857 * n + 0.062767 * n**2 - 0.0020322 * n**3)
        if 1 - w <= 0 or gamma - math.log(1 - w) <= 0:
            return {"w": w, "p": 1.0 if w >= 1 else 0.0}
        z = (-math.log(gamma - math.log(1 - w)) - mu) / sigma
    else:
        ln = math.log(n)
        mu = -1.5861 - 0.31082 * ln - 0.083751 * ln**2 + 0.0038915 * ln**3
        sigma = math.exp(-0.4803 - 0.082676 * ln + 0.0030302 * ln**2)
        if 1 - w <= 0:
            return {"w": w, "p": 1.0}
        z = (math.log(1 - w) - mu) / sigma
    return {"w": w, "p": 1 - normal_cdf(z)}


def levene(*samples):
    """Levene testi Braun–Forsayt varianti (mediana atrofida): dispersiyalar tengligi. p < 0.05 — teng emas."""
    samples = [list(sample) for sample in samples if len(sample) >= 2]
    if len(samples) < 2:
        return None
    deviations = []
    for sample in samples:
        ordered = sorted(sample)
        middle = len(ordered) // 2
        median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
        deviations.append([abs(value - median) for value in sample])
    n = sum(len(group) for group in deviations)
    k = len(deviations)
    grand = sum(map(sum, deviations)) / n
    between = sum(len(group) * (_mean(group) - grand) ** 2 for group in deviations)
    within = sum((value - _mean(group)) ** 2 for group in deviations for value in group)
    if within == 0:
        return None
    f = (n - k) * between / ((k - 1) * within)
    return {"f": f, "df1": k - 1, "df2": n - k, "p": f_sf(f, k - 1, n - k)}


def student_t_test(a, b):
    """Ikki mustaqil tanlanma: Styudent t-testi (dispersiyalar teng deb), Koen d va Xedjes g."""
    if len(a) < 2 or len(b) < 2:
        return None
    df = len(a) + len(b) - 2
    pooled_var = ((len(a) - 1) * _variance(a) + (len(b) - 1) * _variance(b)) / df
    if pooled_var == 0:
        return None
    diff = _mean(a) - _mean(b)
    t = diff / math.sqrt(pooled_var * (1 / len(a) + 1 / len(b)))
    d = diff / math.sqrt(pooled_var)
    correction = _hedges_correction(len(a) + len(b))
    return {"t": t, "df": df, "p": t_two_sided_p(t, df), "cohens_d": d, "hedges_g": d * correction}


def wilcoxon_signed_rank(before, after):
    """Uilkokson ishorali ranglar testi (juftlangan, normal yaqinlashish, bir xil qiymatlar tuzatmasi bilan).

    Nol farqlar tashlab yuboriladi. Effekt hajmi r = |z| / √n.
    """
    diffs = [y - x for x, y in zip(before, after) if y != x]
    n = len(diffs)
    if n < 2:
        return None
    ranks, ties = _ranks([abs(value) for value in diffs])
    w_plus = sum(rank for rank, diff in zip(ranks, diffs) if diff > 0)
    variance = n * (n + 1) * (2 * n + 1) / 24 - sum(t**3 - t for t in ties) / 48
    if variance <= 0:
        return None
    z = (w_plus - n * (n + 1) / 4) / math.sqrt(variance)
    return {"n": n, "w_plus": w_plus, "z": z, "p": normal_two_sided_p(z), "r": abs(z) / math.sqrt(n), "approximate": n < 10}


def _solve(matrix, vector):
    """Kichik chiziqli sistema (Gauss usuli, tanlab bosh element bilan). Yechim yo'q bo'lsa None."""
    size = len(vector)
    rows = [list(row) + [value] for row, value in zip(matrix, vector)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda index: abs(rows[index][col]))
        if abs(rows[pivot][col]) < 1e-12:
            return None
        rows[col], rows[pivot] = rows[pivot], rows[col]
        for index in range(size):
            if index != col:
                factor = rows[index][col] / rows[col][col]
                rows[index] = [x - factor * y for x, y in zip(rows[index], rows[col])]
    return [rows[index][size] / rows[index][index] for index in range(size)]


def _ols_sse(columns, y):
    """Eng kichik kvadratlar: qoldiq kvadratlar yig'indisi va koeffitsiyentlar (birinchi ustun — 1 lar)."""
    k = len(columns)
    xtx = [[sum(a * b for a, b in zip(columns[i], columns[j])) for j in range(k)] for i in range(k)]
    xty = [sum(a * b for a, b in zip(columns[i], y)) for i in range(k)]
    beta = _solve(xtx, xty)
    if beta is None:
        return None, None
    fitted = [sum(beta[j] * columns[j][row] for j in range(k)) for row in range(len(y))]
    return sum((value - fit) ** 2 for value, fit in zip(y, fitted)), beta


def ancova(groups):
    """Bir omilli kovariatsion tahlil (ANCOVA): chiqish natijasi ~ guruh + kirish natijasi.

    groups — {nom: [(kirish, chiqish), ...]} (2 ta guruh). Kirish testidagi boshlang'ich farqni hisobga olib
    guruhlarni solishtiradi: F, p, qisman η², tuzatilgan o'rtachalar, ularning farqi (birinchi guruh − ikkinchi) va
    uning ishonch oralig'i, regressiya chiziqlari parallelligi (guruh × kirish o'zaro ta'siri; p < 0.05 bo'lsa ANCOVA
    sharti buzilgan). Xedjes g — tuzatilgan farq / chiqish testining birlashgan SD si (WWC usuli).
    """
    names = list(groups)
    if len(names) != 2 or any(len(groups[name]) < 2 for name in names):
        return None
    pre = [x for name in names for x, _ in groups[name]]
    post = [y for name in names for _, y in groups[name]]
    group = [1.0 if index < len(groups[names[0]]) else 0.0 for index in range(len(pre))]
    n = len(pre)
    if n < 5:
        return None
    ones = [1.0] * n
    sse_full, beta = _ols_sse([ones, group, pre], post)
    sse_reduced, _ = _ols_sse([ones, pre], post)
    interaction = [g * x for g, x in zip(group, pre)]
    sse_interaction, _ = _ols_sse([ones, group, pre, interaction], post)
    sse_group_on_pre, _ = _ols_sse([ones, pre], group)
    if sse_full is None or sse_reduced is None or sse_full <= 0:
        return None
    df_error = n - 3
    ss_group = max(0.0, sse_reduced - sse_full)
    f = ss_group / (sse_full / df_error)
    slopes = None
    if sse_interaction is not None and sse_interaction > 0 and n > 4:
        f_slopes = max(0.0, sse_full - sse_interaction) / (sse_interaction / (n - 4))
        slopes = {"f": f_slopes, "df1": 1, "df2": n - 4, "p": f_sf(f_slopes, 1, n - 4)}
    # Guruh koeffitsiyenti xatosi: guruh ustunining kirish testidan mustaqil qismi bo'yicha (Friš–Vo teoremasi)
    ci = None
    if sse_group_on_pre:
        half = _t_ppf(1 - ALPHA / 2, df_error) * math.sqrt(sse_full / df_error / sse_group_on_pre)
        ci = (beta[1] - half, beta[1] + half)
    pooled = _pooled_sd(*[[y for _, y in groups[name]] for name in names])
    hedges_g = None
    if pooled and ci:
        scale = _hedges_correction(n) / pooled
        hedges_g = {"value": beta[1] * scale, "ci": (ci[0] * scale, ci[1] * scale)}
    grand_pre = _mean(pre)
    adjusted = {
        name: _mean([y for _, y in groups[name]]) - beta[2] * (_mean([x for x, _ in groups[name]]) - grand_pre)
        for name in names
    }
    return {
        "f": f,
        "df1": 1,
        "df2": df_error,
        "p": f_sf(f, 1, df_error),
        "partial_eta2": ss_group / (ss_group + sse_full),
        "slope": beta[2],
        "beta": beta,
        "adjusted_means": adjusted,
        "adjusted_diff": beta[1],
        "adjusted_diff_ci": ci,
        "hedges_g": hedges_g,
        "slopes_homogeneity": slopes,
    }


def required_n_per_group(d, alpha=ALPHA, power=0.8):
    """Ikki mustaqil guruhni t-test bilan solishtirish uchun har bir guruhda kerakli talabalar soni
    (normal yaqinlashish + Guenther tuzatmasi; G*Power natijasidan odatda 1 ta farq qiladi)."""
    if not d:
        return None
    z_alpha = normal_ppf(1 - alpha / 2)
    z_beta = normal_ppf(power)
    return math.ceil(2 * ((z_alpha + z_beta) / abs(d)) ** 2 + z_alpha**2 / 4)


def achieved_power(d, n1, n2, alpha=ALPHA):
    """Berilgan effekt hajmi va guruh o'lchamlarida t-testning quvvati (normal yaqinlashish)."""
    if not d or n1 < 2 or n2 < 2:
        return None
    z_alpha = normal_ppf(1 - alpha / 2)
    shift = abs(d) * math.sqrt(n1 * n2 / (n1 + n2))
    return normal_cdf(shift - z_alpha) + normal_cdf(-shift - z_alpha)


def holm(pvalues):
    """Xolm–Bonferroni tuzatishi: tuzatilgan p-qiymatlar (kirish tartibida). None qiymatlar o'zgarishsiz qoladi."""
    present = sorted((p, index) for index, p in enumerate(pvalues) if p is not None)
    adjusted = list(pvalues)
    m = len(present)
    running = 0.0
    for rank, (p, index) in enumerate(present):
        running = max(running, min(1.0, (m - rank) * p))
        adjusted[index] = running
    return adjusted


def icc_oneway(samples):
    """Bir omilli ANOVA bo'yicha sinfichi korrelyatsiya ICC(1) (klasterlar o'lchami har xil bo'lishi mumkin).

    samples — klasterlar (masalan, akademik guruhlar) bo'yicha qiymatlar ro'yxati. ICC = (MSB − MSW) / (MSB + (k₀ − 1)·MSW),
    k₀ — tuzatilgan o'rtacha klaster o'lchami. Manfiy baho 0 deb olinadi (Donner, 1986). Kamida 2 ta klaster kerak.
    """
    samples = [list(sample) for sample in samples if sample]
    k = len(samples)
    n = sum(len(sample) for sample in samples)
    if k < 2 or n - k < 1:
        return None
    grand = sum(map(sum, samples)) / n
    between = sum(len(sample) * (_mean(sample) - grand) ** 2 for sample in samples)
    within = sum((value - _mean(sample)) ** 2 for sample in samples for value in sample)
    msb, msw = between / (k - 1), within / (n - k)
    k0 = (n - sum(len(sample) ** 2 for sample in samples) / n) / (k - 1)
    denominator = msb + (k0 - 1) * msw
    if denominator <= 0:
        return None
    icc = max(0.0, (msb - msw) / denominator)
    f = msb / msw if msw else None
    mean_size = n / k
    design_effect = 1 + (mean_size - 1) * icc
    return {
        "icc": icc,
        "f": f,
        "df1": k - 1,
        "df2": n - k,
        "p": f_sf(f, k - 1, n - k) if f is not None else None,
        "clusters": k,
        "mean_size": mean_size,
        "design_effect": design_effect,
        "effective_n": n / design_effect,
    }


def tost(a, b, margin, alpha=ALPHA):
    """Ikki mustaqil o'rtachaning ekvivalentligi (Shuirmann TOST, Uelch shaklida): |M_a − M_b| < margin.

    Ikkala bir tomonlama test p < α bo'lsa — ekvivalent. p_tost = ikkalasining kattasi. Shu bilan birga
    (1 − 2α) ishonch oralig'i qaytariladi: u (−margin, margin) ichida bo'lsa, ekvivalentlik isbotlangan.
    """
    if len(a) < 2 or len(b) < 2 or margin <= 0:
        return None
    var_a, var_b = _variance(a), _variance(b)
    se2 = var_a / len(a) + var_b / len(b)
    if se2 == 0:
        return None
    se = math.sqrt(se2)
    df = se2**2 / ((var_a / len(a)) ** 2 / (len(a) - 1) + (var_b / len(b)) ** 2 / (len(b) - 1))
    diff = _mean(a) - _mean(b)

    def upper_tail(t):
        """P(T > t) Styudent taqsimotida."""
        half = t_two_sided_p(t, df) / 2
        return half if t >= 0 else 1 - half

    p_lower = upper_tail((diff + margin) / se)  # H0: diff ≤ −margin
    p_upper = 1 - upper_tail((diff - margin) / se)  # H0: diff ≥ margin
    t_crit = _t_ppf(1 - alpha, df)
    p = max(p_lower, p_upper)
    return {
        "diff": diff,
        "margin": margin,
        "df": df,
        "p_lower": p_lower,
        "p_upper": p_upper,
        "p": p,
        "ci": (diff - t_crit * se, diff + t_crit * se),
        "equivalent": p < alpha,
    }


def _t_ppf(q, df):
    """Styudent taqsimoti kvantili (bisektsiya, P(T ≤ t) = q, q > 0.5)."""
    low, high = 0.0, 1000.0
    for _ in range(200):
        middle = (low + high) / 2
        if 1 - t_two_sided_p(middle, df) / 2 < q:
            low = middle
        else:
            high = middle
    return (low + high) / 2
