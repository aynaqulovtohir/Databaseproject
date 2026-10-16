"""Ko'chirishni aniqlash: bir laboratoriyadagi talabalar yechimlarining o'xshashligi.

To'g'ri yechimlar tabiiy ravishda bir-biriga (va namunaga) o'xshaydi, shuning uchun faqat talabaning
o'z tanlovlari solishtiriladi — namunaviy yechimda yo'q bo'laklar:
- SQL: kod tokenlarining 3-gramlari (kalit so'zlar va nomlar kichik harfda) va izohlar matni;
- ER: obyekt, atribut ("obyekt.atribut") va bog'lanish nomlari.
O'xshashlik — shu bo'laklar to'plamlarining Jakkar koeffitsienti (umumiy / jami).

Qo'shimcha signal: ikki talabada bir xil xato urinish (uzun kod, uni boshqa ko'p talaba qilmagan).
Natija dalil emas, faqat o'qituvchi qo'lda tekshirishi uchun belgi.
"""
import hashlib
import re
from collections import defaultdict
from itertools import combinations

from .er import normalize

THRESHOLD = 0.6
# Shundan kam o'z tanlovi bo'lgan ish solishtirilmaydi (masalan, namunaning aynan o'zi)
MIN_FEATURES = 6
NGRAM = 3
# Bir xil xato urinish shundan qisqa bo'lsa yoki shuncha ko'p talabada uchrasa — tasodif deb hisoblanadi
MIN_WRONG_LENGTH = 60
MAX_WRONG_SHARERS = 3
MAX_PAIRS = 50

TOKEN = re.compile(r"'(?:[^']|'')*'|\"[^\"]*\"|\d+(?:\.\d+)?|[^\W\d]\w*|<>|!=|<=|>=|::|\S", re.UNICODE)
LINE_COMMENT = re.compile(r"--([^\n]*)")
BLOCK_COMMENT = re.compile(r"/\*(.*?)\*/", re.S)


def _comments(code):
    found = LINE_COMMENT.findall(code) + BLOCK_COMMENT.findall(code)
    return {" ".join(text.lower().split()) for text in found if len(text.strip()) >= 4}


def _tokens(code):
    code = BLOCK_COMMENT.sub(" ", LINE_COMMENT.sub(" ", code))
    # Matnli qiymatlar katta-kichik harfi saqlanadi, qolganlari kichik harfga
    return [token if token.startswith("'") else token.lower() for token in TOKEN.findall(code)]


def _ngrams(tokens):
    return {" ".join(tokens[index : index + NGRAM]) for index in range(len(tokens) - NGRAM + 1)}


def sql_features(code, reference=""):
    own = _ngrams(_tokens(code)) - _ngrams(_tokens(reference))
    return {f"k:{gram}" for gram in own} | {f"i:{text}" for text in _comments(code) - _comments(reference)}


def _diagram_names(diagram):
    names = set()
    if not isinstance(diagram, dict):
        return names
    entities = {}
    for entity in diagram.get("entities") or []:
        name = normalize(str(entity.get("name", "")))
        entities[entity.get("id")] = name
        names.add(f"o:{name}")
        for attribute in entity.get("attributes") or []:
            names.add(f"a:{name}.{normalize(str(attribute.get('name', '')))}")
    for relationship in diagram.get("relationships") or []:
        names.add(f"b:{normalize(str(relationship.get('name', '')))}")
    return names


def er_features(diagram, reference=None):
    return _diagram_names(diagram) - _diagram_names(reference)


def jaccard(first, second):
    union = first | second
    return len(first & second) / len(union) if union else 0.0


def _code_hash(code):
    return hashlib.sha256(" ".join(_tokens(code)).encode()).hexdigest()


def find_similar(lab, attempts_by_student):
    """attempts_by_student: {talaba_id: [urinishlar vaqt bo'yicha]}.

    Qaytaradi: (o'xshash juftliklar ro'yxati, solishtirilgan talabalar soni).
    Juftlik: {"students": (a, b), "score", "shared", "shared_wrong", "gap_minutes"}."""
    if lab.kind == "norm":
        # Normallashtirishda to'g'ri javob hammada bir xil: o'xshashlik ko'chirish belgisi emas
        return [], 0
    features, solved_at = {}, {}
    for student_id, attempts in attempts_by_student.items():
        correct = [attempt for attempt in attempts if attempt.is_correct]
        final = (correct or attempts)[-1]
        if lab.kind == "er":
            own = er_features(final.diagram, lab.reference_diagram)
        else:
            own = sql_features(final.sql_code, lab.solution_sql)
        if len(own) >= MIN_FEATURES:
            features[student_id] = own
        if correct:
            solved_at[student_id] = correct[0].created_at

    # Bir xil uzun xato urinishlar (faqat SQL: ER diagrammasida "kod" yo'q)
    wrong_sharers = defaultdict(set)
    if lab.kind != "er":
        for student_id, attempts in attempts_by_student.items():
            for attempt in attempts:
                if not attempt.is_correct and len(attempt.sql_code.strip()) >= MIN_WRONG_LENGTH:
                    wrong_sharers[_code_hash(attempt.sql_code)].add(student_id)
    shared_wrong = defaultdict(int)
    for sharers in wrong_sharers.values():
        if 2 <= len(sharers) <= MAX_WRONG_SHARERS:
            for pair in combinations(sorted(sharers), 2):
                shared_wrong[pair] += 1

    pairs = []
    candidates = set(combinations(sorted(features), 2)) | set(shared_wrong)
    for first, second in candidates:
        score = jaccard(features.get(first, set()), features.get(second, set()))
        wrong = shared_wrong.get((first, second), 0)
        if score < THRESHOLD and not wrong:
            continue
        gap = None
        if first in solved_at and second in solved_at:
            gap = round(abs((solved_at[first] - solved_at[second]).total_seconds()) / 60, 1)
        pairs.append(
            {
                "students": (first, second),
                "score": round(score, 2),
                "shared": len(features.get(first, set()) & features.get(second, set())),
                "shared_wrong": wrong,
                "gap_minutes": gap,
            }
        )
    pairs.sort(key=lambda pair: (pair["score"], pair["shared_wrong"]), reverse=True)
    return pairs[:MAX_PAIRS], len(features)
