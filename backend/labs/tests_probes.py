"""Yaxlitlik cheklovlari laboratoriyasi: sinovlar tuzilishi, saqlashdagi tekshiruv, aldash yo'llari va baho.

Testlar haqiqiy qum quti bazasida (LAB_SANDBOX_DB) bajariladi.
"""
from django.test import SimpleTestCase, override_settings
from rest_framework import status

from .models import Lab, LabGrade
from .probes import ProbesError, validate_probes
from .sandbox import SqlError
from .tests import BaseTestCase

SETUP = """
CREATE TABLE kategoriya (id INT PRIMARY KEY, nomi TEXT);
INSERT INTO kategoriya VALUES (1, 'Kitob');
CREATE TABLE mahsulot (id INT PRIMARY KEY, nomi TEXT, narx INT, kategoriya_id INT);
INSERT INTO mahsulot VALUES (1, 'Alifbo', 10, 1);
"""
CONSTRAINTS = """
ALTER TABLE mahsulot ALTER COLUMN nomi SET NOT NULL;
ALTER TABLE mahsulot ADD CHECK (narx > 0);
ALTER TABLE mahsulot ADD UNIQUE (nomi);
ALTER TABLE mahsulot ADD FOREIGN KEY (kategoriya_id) REFERENCES kategoriya (id);
"""
PROBES = [
    {"id": "a1", "title": "Manfiy narx", "kind": "attack", "sql": "INSERT INTO mahsulot VALUES (2, 'Daftar', -5, 1)"},
    {"id": "a2", "title": "Nomsiz mahsulot", "kind": "attack", "sql": "INSERT INTO mahsulot VALUES (3, NULL, 5, 1)"},
    {"id": "a3", "title": "Takror nom", "kind": "attack", "sql": "INSERT INTO mahsulot VALUES (4, 'Alifbo', 5, 1)"},
    {"id": "a4", "title": "Yo'q kategoriya", "kind": "attack", "sql": "INSERT INTO mahsulot VALUES (5, 'Ruchka', 5, 99)"},
    {"id": "v1", "title": "Oddiy mahsulot", "kind": "valid", "sql": "INSERT INTO mahsulot VALUES (6, 'Qalam', 3, 1)"},
    # Oldingi sinov orqaga qaytarilgani uchun xuddi shu qator yana qabul qilinadi
    {"id": "v2", "title": "Xuddi shu mahsulot yana", "kind": "valid", "sql": "INSERT INTO mahsulot VALUES (6, 'Qalam', 3, 1)"},
    {"id": "h1", "title": "Narxni nolga tushirish", "kind": "attack", "sql": "UPDATE mahsulot SET narx = 0 WHERE id = 1",
     "hidden": True},
]


class ProbeStructureTests(SimpleTestCase):
    def test_validation(self):
        clean = validate_probes([{**PROBES[0], "title": "  Manfiy   narx ", "extra": 1}])
        self.assertEqual(clean, [{**PROBES[0], "hidden": False}])
        for bad in (
            "x",
            [{**PROBES[0], "kind": "boshqa"}],
            [PROBES[0], PROBES[0]],
            [{**PROBES[0], "id": "a b"}],
            [{**PROBES[0], "sql": " "}],
            [PROBES[4]],  # birorta hujum yo'q
            [{**PROBES[0], "sql": "INSERT INTO mahsulot VALUES (2, 'x', -5, 1); COMMIT"}],
            [{**PROBES[0], "sql": "ROLLBACK; INSERT INTO mahsulot VALUES (2, 'x', -5, 1)"}],
        ):
            with self.subTest(bad=bad), self.assertRaises(ProbesError):
                validate_probes(bad)
        # Matn ichidagi so'z tranzaksiya buyrug'i emas
        validate_probes([{**PROBES[0], "sql": "INSERT INTO kategoriya VALUES (7, 'COMMIT; xato')"}])


@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="")
class ProbeLabTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.probe_lab = Lab.objects.create(
            title="Do'kon cheklovlari",
            description="Mahsulot jadvaliga cheklovlar qo'shing",
            setup_sql=SETUP,
            solution_sql=CONSTRAINTS,
            probes=validate_probes(PROBES),
            author=cls.teacher_a,
        )
        cls.probe_lab.groups.add(cls.group_a)
        cls.probe_run_url = f"/api/labs/{cls.probe_lab.pk}/run/"

    def check(self, code):
        self.auth_as(self.student_a1)
        response = self.run_code(code, self.probe_run_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data

    def test_correct_constraints_pass_every_probe(self):
        data = self.check(CONSTRAINTS)
        self.assertTrue(data["is_correct"], data)
        self.assertEqual(data["ratio"], 1.0)
        self.assertEqual([item["id"] for item in data["probes"]], ["a1", "a2", "a3", "a4", "v1", "v2"])
        self.assertTrue(all(item["passed"] for item in data["probes"]))
        # Rad etilgan hujumda cheklov xabari ko'rsatiladi
        self.assertIn("check", data["probes"][0]["message"].lower())
        self.assertEqual(data["hidden_probes"], {"total": 1, "passed": 1})
        self.assertEqual(self.probe_lab.effective_topic, Lab.Topic.INTEGRITY)

    def test_narrow_check_is_caught_by_hidden_probe(self):
        narrow = CONSTRAINTS.replace("CHECK (narx > 0)", "CHECK (narx <> -5)")
        data = self.check(narrow)
        self.assertFalse(data["is_correct"])
        self.assertTrue(all(item["passed"] for item in data["probes"]))
        self.assertEqual(data["hidden_probes"], {"total": 1, "passed": 0})
        self.assertIn("Yashirin", data["differences"][0])
        # Yashirin sinov nomi va SQL'i oshkor qilinmaydi
        self.assertNotIn("nolga", str(data))

    def test_blocking_everything_fails_valid_probes(self):
        trigger = """
        CREATE FUNCTION taqiq() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'hech narsa mumkin emas'; END $$;
        CREATE TRIGGER t BEFORE INSERT OR UPDATE ON mahsulot FOR EACH ROW EXECUTE FUNCTION taqiq();
        """
        data = self.check(trigger)
        self.assertFalse(data["is_correct"])
        attacks = [item for item in data["probes"] if item["kind"] == "attack"]
        self.assertTrue(all(item["passed"] for item in attacks))
        valid = [item for item in data["probes"] if item["kind"] == "valid"]
        self.assertFalse(any(item["passed"] for item in valid))
        self.assertIn("hech narsa mumkin emas", valid[0]["message"])

    def test_dropping_the_table_does_not_count_as_blocking(self):
        data = self.check("DROP TABLE mahsulot;")
        self.assertFalse(data["is_correct"])
        self.assertEqual(data["ratio"], 0.0)

    def test_student_code_error(self):
        data = self.check("ALTER TABLE yoq ADD CHECK (x > 0);")
        self.assertFalse(data["is_correct"])
        self.assertIsNotNone(data["error"])
        self.assertEqual(data["probes"], [])

    def test_submit_scores_by_share_of_passed_probes(self):
        self.auth_as(self.student_a1)
        url = f"/api/labs/{self.probe_lab.pk}/submit/"
        partial = "ALTER TABLE mahsulot ADD CHECK (narx > 0);"  # 3 ta hujum o'tadi: 4/7 sinov
        response = self.client.post(url, {"sql_code": partial}, format="json")
        self.assertEqual(response.data["grade"]["score"], round(60 * 4 / 7))
        self.assertEqual(response.data["grade"]["source"], LabGrade.Source.AUTO)
        response = self.client.post(url, {"sql_code": CONSTRAINTS}, format="json")
        self.assertEqual(response.data["grade"]["score"], 100)

    def test_student_sees_visible_probes_only(self):
        self.auth_as(self.student_a1)
        probes = self.client.get(f"/api/labs/{self.probe_lab.pk}/").data["probe_info"]
        self.assertEqual(len(probes["visible"]), 6)
        self.assertEqual(probes["hidden"], 1)
        self.assertNotIn("UPDATE", str(probes))
        self.assertIsNone(self.client.get(self.url).data["probe_info"])

    def test_teacher_saving_validates_probes(self):
        self.auth_as(self.teacher_a)
        data = {
            "kind": "sql",
            "title": "Cheklovlar",
            "description": "d",
            "setup_sql": SETUP,
            "solution_sql": CONSTRAINTS,
            "probes": PROBES,
            "groups": [self.group_a.pk],
        }
        response = self.client.post("/api/labs/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(len(response.data["probes"]), 7)

        # Cheklovsiz ham bajarilmaydigan "hujum" (asosiy kalit takrori) — sinov bo'la olmaydi
        broken = PROBES + [{"id": "pk", "title": "Takror id", "kind": "attack", "sql": "INSERT INTO mahsulot VALUES (1, 'X', 1, 1)"}]
        response = self.client.post("/api/labs/", {**data, "probes": broken}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cheklovsiz ham bajarilmadi", str(response.data["probes"]))

        # Namunaviy yechim hujumni to'xtatmaydi
        weak = CONSTRAINTS.replace("ALTER TABLE mahsulot ADD UNIQUE (nomi);", "")
        response = self.client.post("/api/labs/", {**data, "solution_sql": weak}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Takror nom", str(response.data["probes"]))

        response = self.client.post("/api/labs/", {**data, "probes": [{"id": "x"}]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post("/api/labs/", {**data, "concurrent": True}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_probe_time_budget(self):
        from unittest.mock import patch

        with patch("labs.sandbox.PROBES_TIME_BUDGET_SECONDS", 0):
            data = self.check(CONSTRAINTS)
        self.assertFalse(data["is_correct"])
        self.assertIn("vaqt", data["probes"][0]["message"].lower())

    def test_message_has_no_line_number(self):
        from .probes import message

        self.assertEqual(message(SqlError("xato", detail="tafsilot", line=2)), "xato (tafsilot)")


class ReadyIntegrityLabsTests(BaseTestCase):
    def test_ready_labs_are_valid_and_solutions_pass(self):
        from .checker import check_code
        from .integrity_labs import INTEGRITY_LABS
        from .probes import validate_lab_probes

        for data in INTEGRITY_LABS:
            with self.subTest(lab=data["title"]):
                probes = validate_probes(data["probes"])
                validate_lab_probes(data["setup_sql"], data["solution_sql"], probes)
                self.assertTrue(any(probe["hidden"] for probe in probes))
                lab = Lab(setup_sql=data["setup_sql"], solution_sql=data["solution_sql"], probes=probes)
                self.assertTrue(check_code(lab, data["solution_sql"])["is_correct"])

    def test_insert_only_trigger_is_caught(self):
        """Universitet: faqat INSERT ni tekshiradigan trigger yozilishni boshqa semestrga ko'chirishni (UPDATE) o'tkazib yuboradi."""
        from .checker import check_code
        from .integrity_labs import INTEGRITY_LABS

        data = INTEGRITY_LABS[2]
        lab = Lab(setup_sql=data["setup_sql"], solution_sql=data["solution_sql"], probes=validate_probes(data["probes"]))
        insert_only = data["solution_sql"].replace("AFTER INSERT OR UPDATE", "AFTER INSERT")
        result = check_code(lab, insert_only)
        self.assertFalse(result["is_correct"])
        self.assertTrue(all(item["passed"] for item in result["probes"]))
        self.assertEqual(result["hidden_probes"]["passed"], result["hidden_probes"]["total"] - 1)

    def test_failed_probes_have_research_categories(self):
        from .research import difference_category

        self.assertEqual(difference_category("«Takror nom» — o'tib ketdi."), "cheklov_hujum_otdi")
        self.assertEqual(difference_category("«Oddiy» — rad etildi, lekin u to'g'ri ma'lumot."), "cheklov_togri_rad_etildi")
        self.assertEqual(difference_category("Yashirin sinovlardan 1 tasi o'tmadi: ..."), "cheklov_yashirin_sinov")
