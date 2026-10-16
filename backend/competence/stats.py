"""Tajriba samaradorligi uchun statistik mezonlar (toza Python, tashqi kutubxonasiz).

- Pirson χ² (darajalar taqsimoti: tajriba va nazorat guruhlari), Kramer V — effekt hajmi;
- Styudent t-testi (Uelch varianti: dispersiyalar teng bo'lishi shart emas), Koen d va Xedjes g;
- Mann–Uitni U testi (normal yaqinlashish, bir xil qiymatlar tuzatmasi bilan) — taqsimot normal bo'lmasa;
- juftlangan t-test — bitta guruhning tajriba boshi va oxiri (o'sish).

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
    correction = 1 - 3 / (4 * (len(a) + len(b)) - 9)
    return {"t": t, "df": df, "p": t_two_sided_p(t, df), "cohens_d": d, "hedges_g": d * correction if d is not None else None}


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
    variance = n1 * n2 / 12 * ((n + 1) - sum(t**3 - t for t in ties) / (n * (n - 1)))
    if variance <= 0:
        return None
    z = (u - n1 * n2 / 2) / math.sqrt(variance)
    return {"u": u, "z": z, "p": normal_two_sided_p(z), "approximate": min(n1, n2) < 8}


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
