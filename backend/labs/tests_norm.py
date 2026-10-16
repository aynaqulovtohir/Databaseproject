"""Normallashtirish laboratoriyasi: algoritmlar va API (AI'siz, hisoblab tekshiriladi)."""
from django.test import SimpleTestCase, override_settings
from rest_framework import status

from .models import Lab, LabAttempt, LabGrade
from .norm import (
    NormError,
    candidate_keys,
    check,
    closure,
    lossless,
    normal_form,
    parse_answer,
    parse_task,
    preserves,
    reference_solution,
)
from .tests import BaseTestCase

ATTRIBUTES = "talaba_id, ism, fan_id, fan_nomi, kafedra, baho"
FDS = "talaba_id -> ism\nfan_id -> fan_nomi, kafedra\ntalaba_id, fan_id -> baho"
CORRECT = {
    "keys": ["talaba_id, fan_id"],
    "normal_form": "1NF",
    "decomposition": ["talaba(talaba_id, ism)", "fan(fan_id, fan_nomi, kafedra)", "baho(talaba_id, fan_id, baho)"],
}


def fd(lhs, rhs):
    return frozenset(lhs), frozenset(rhs)


class NormAlgorithmTests(SimpleTestCase):
    def test_closure_and_keys(self):
        fds = [fd("a", "b"), fd("b", "c")]
        self.assertEqual(closure({"a"}, fds), frozenset("abc"))
        self.assertEqual(candidate_keys("abcd", fds), [frozenset("ad")])
        # Ikki kalit: {a, b} va {a, c}
        self.assertEqual(sorted(map(sorted, candidate_keys("abc", [fd("ab", "c"), fd("c", "b")]))), [["a", "b"], ["a", "c"]])

    def test_normal_forms(self):
        self.assertEqual(normal_form("abc", [fd("a", "bc")]), "BCNF")
        self.assertEqual(normal_form("abc", [fd("a", "b"), fd("b", "c")]), "2NF")  # tranzitiv
        self.assertEqual(normal_form("abcd", [fd("ab", "c"), fd("a", "d")]), "1NF")  # qisman
        self.assertEqual(normal_form("abc", [fd("ab", "c"), fd("c", "b")]), "3NF")  # BCNF emas, b — asosiy

    def test_lossless_and_preservation(self):
        fds = [fd("a", "b"), fd("b", "c")]
        self.assertTrue(lossless("abc", fds, [frozenset("ab"), frozenset("bc")]))
        # Umumiy atribut a — {a, b} jadvalining kaliti: yo'qotishsiz (lekin b -> c saqlanmaydi)
        self.assertTrue(lossless("abc", fds, [frozenset("ab"), frozenset("ac")]))
        self.assertFalse(lossless("abcd", fds, [frozenset("ab"), frozenset("cd")]))
        self.assertEqual(preserves(fds, [frozenset("ab"), frozenset("bc")]), [])
        self.assertEqual(preserves(fds, [frozenset("ab"), frozenset("ac")]), [fd("b", "c")])

    def test_reference_solution_passes_its_own_check(self):
        for target in ("3NF", "BCNF"):
            task = parse_task(ATTRIBUTES, FDS, target)
            self.assertEqual(check(task, reference_solution(task))["differences"], [])
        task = parse_task("a, b, c", "a, b -> c\nc -> b", "BCNF")
        self.assertEqual(check(task, reference_solution(task))["differences"], [])

    def test_answer_does_not_reveal_missing_keys(self):
        task = parse_task("a, b, c", "a, b -> c\nc -> b", "3NF")
        answer = parse_answer({"keys": ["a, b"], "normal_form": "3NF", "decomposition": ["a, b, c"]}, task)
        result = check(task, answer)
        text = " ".join(result["differences"])
        self.assertIn("yana 1 ta kalit bor", text)
        self.assertNotIn("{a, c}", text)
        self.assertEqual(result["ratio"], 0.7)

    def test_task_and_answer_validation(self):
        for attributes, fds, target in (
            ("a", "a -> a", "3NF"),
            ("a, b", "a -> c", "3NF"),
            ("a, b", "a b", "3NF"),
            ("a, a", "a -> a", "3NF"),
            ("a, b", "a -> b", "4NF"),
            ("a; drop", "a -> b", "3NF"),
            (", ".join(f"x{i}" for i in range(13)), "x0 -> x1", "3NF"),
        ):
            with self.assertRaises(NormError, msg=(attributes, fds, target)):
                parse_task(attributes, fds, target)
        task = parse_task("a, b", "a -> b", "3NF")
        for bad in ({"keys": ["z"], "normal_form": "BCNF", "decomposition": ["a, b"]}, {"keys": ["a"]}, "x"):
            with self.assertRaises(NormError):
                parse_answer(bad, task)


@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="")
class NormLabApiTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.norm_lab = Lab.objects.create(
            kind=Lab.Kind.NORM,
            title="Baholar jadvali",
            description="Jadvalni 3NF ga keltiring",
            norm_task=parse_task(ATTRIBUTES, FDS, "3NF"),
            author=cls.teacher_a,
        )
        cls.norm_lab.groups.add(cls.group_a)
        cls.norm_url = f"/api/labs/{cls.norm_lab.pk}/"

    def test_teacher_creates_lab_from_text_and_sees_reference(self):
        self.auth_as(self.teacher_a)
        response = self.client.post(
            "/api/labs/",
            {
                "kind": "norm",
                "title": "Yangi",
                "description": "x",
                "norm_task": {"attributes": ATTRIBUTES, "fds": FDS, "target": "BCNF"},
                "groups": [self.group_a.pk],
                "solution_sql": "DROP TABLE x",  # normallashtirishda e'tiborga olinmaydi
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["norm_task"]["target"], "BCNF")
        self.assertEqual(response.data["norm_reference"]["keys"], [["fan_id", "talaba_id"]])
        self.assertEqual(response.data["solution_sql"], "")

        bad = self.client.post(
            "/api/labs/",
            {"kind": "norm", "title": "x", "description": "x", "norm_task": {"attributes": "a", "fds": "", "target": "3NF"},
             "groups": [self.group_a.pk]},
            format="json",
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("norm_task", bad.data)

    def test_student_sees_task_without_reference(self):
        self.auth_as(self.student_a1)
        data = self.client.get(self.norm_url).data
        self.assertEqual(data["norm_task"]["attributes"][0], "talaba_id")
        self.assertNotIn("norm_reference", data)

    def test_run_and_submit(self):
        self.auth_as(self.student_a1)
        wrong = {**CORRECT, "normal_form": "2NF"}
        response = self.client.post(f"{self.norm_url}run/", {"answer": wrong}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertFalse(response.data["is_correct"])
        attempt = LabAttempt.objects.get()
        self.assertIn("Hozirgi normal forma: 2NF", attempt.sql_code)
        self.assertEqual(attempt.answer["normal_form"], "2NF")

        response = self.client.post(f"{self.norm_url}submit/", {"answer": wrong}, format="json")
        self.assertEqual(response.data["grade"]["score"], 48)  # 60 * 0.8
        response = self.client.post(f"{self.norm_url}submit/", {"answer": CORRECT}, format="json")
        self.assertTrue(response.data["is_correct"])
        self.assertEqual(LabGrade.objects.get(lab=self.norm_lab).score, 100)
        self.assertEqual(self.client.get(self.norm_url).data["my_progress"]["last_answer"]["normal_form"], "1NF")

    def test_invalid_answer(self):
        self.auth_as(self.student_a1)
        response = self.client.post(f"{self.norm_url}run/", {"answer": {**CORRECT, "keys": ["yoq_atribut"]}}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("munosabatda yo'q", str(response.data))


class NormSeedLabsTests(SimpleTestCase):
    def test_ready_labs_are_solvable_and_teach_different_forms(self):
        from .norm_labs import NORM_LABS

        forms = []
        for lab in NORM_LABS:
            reference = reference_solution(lab["norm_task"])
            self.assertEqual(check(lab["norm_task"], reference)["differences"], [], lab["title"])
            forms.append(reference["normal_form"])
        # Qisman bog'liqlik (1NF), tranzitiv (2NF) va BCNF emas, lekin 3NF
        self.assertEqual(forms, ["1NF", "2NF", "3NF"])
