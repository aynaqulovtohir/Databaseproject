"""Sxemani rivojlantirish (migratsiya) laboratoriyasi: ma'lumot saqlanishi, yangi so'rovlar, yashirin ma'lumotlar."""
from django.test import SimpleTestCase, override_settings
from rest_framework import status

from .evolution import QueriesError, validate_queries
from .models import Lab
from .tests import BaseTestCase

SETUP = """
CREATE TABLE mijoz (id INT PRIMARY KEY, fio VARCHAR(100) NOT NULL);
INSERT INTO mijoz VALUES (1, 'Ali Valiyev'), (2, 'Laylo Karimova'), (3, 'Bobur Valiyev');
"""
HIDDEN = """
CREATE TABLE mijoz (id INT PRIMARY KEY, fio VARCHAR(100) NOT NULL);
INSERT INTO mijoz VALUES (1, 'Sardor Toshev'), (2, 'Madina Valiyeva'), (5, 'Jasur Valiyev'), (9, 'Nilufar Aliyeva');
"""
MIGRATION = """
ALTER TABLE mijoz ADD COLUMN ism VARCHAR(50), ADD COLUMN familiya VARCHAR(50);
UPDATE mijoz SET ism = split_part(fio, ' ', 1), familiya = split_part(fio, ' ', 2);
ALTER TABLE mijoz ALTER COLUMN ism SET NOT NULL, ALTER COLUMN familiya SET NOT NULL;
ALTER TABLE mijoz DROP COLUMN fio;
"""
QUERIES = [
    {"id": "royxat", "title": "Mijozlar ro'yxati", "sql": "SELECT ism, familiya FROM mijoz ORDER BY id"},
    {"id": "familiya", "title": "Familiya bo'yicha qidiruv", "sql": "SELECT count(*) FROM mijoz WHERE familiya = 'Valiyev'"},
]


class QueryStructureTests(SimpleTestCase):
    def test_multi_statement_query_ends_with_select(self):
        clean = validate_queries([{"id": "t", "title": "Trigger", "sql": "UPDATE mijoz SET fio = 'x' WHERE id = 1;\nSELECT 1;"}])
        self.assertEqual(clean[0]["sql"], "UPDATE mijoz SET fio = 'x' WHERE id = 1;\nSELECT 1")

    def test_validation(self):
        self.assertEqual(validate_queries([{**QUERIES[0], "title": " Mijozlar  ro'yxati ", "sql": QUERIES[0]["sql"] + ";"}]), [QUERIES[0]])
        for bad in (
            "x",
            [{**QUERIES[0], "id": "a b"}],
            [QUERIES[0], QUERIES[0]],
            [{**QUERIES[0], "sql": "UPDATE mijoz SET fio = 'x'"}],
            [{**QUERIES[0], "sql": "BEGIN; SELECT 1"}],
            [{**QUERIES[0], "sql": "COMMIT"}],
            [{**QUERIES[0], "title": ""}],
        ):
            with self.subTest(bad=bad), self.assertRaises(QueriesError):
                validate_queries(bad)


@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="")
class EvolutionLabTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.evolution_lab = Lab.objects.create(
            title="Ism va familiya",
            description="fio ustunini ism va familiyaga ajrating",
            setup_sql=SETUP,
            solution_sql=MIGRATION,
            hidden_setup_sql=HIDDEN,
            check_queries=QUERIES,
            author=cls.teacher_a,
        )
        cls.evolution_lab.groups.add(cls.group_a)
        cls.evolution_url = f"/api/labs/{cls.evolution_lab.pk}/run/"

    def check(self, code):
        self.auth_as(self.student_a1)
        response = self.run_code(code, self.evolution_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data

    def test_correct_migration(self):
        data = self.check(MIGRATION)
        self.assertTrue(data["is_correct"], data)
        self.assertEqual([item["passed"] for item in data["queries"]], [True, True])
        self.assertEqual(self.evolution_lab.effective_topic, Lab.Topic.EVOLUTION)

    def test_data_loss_is_detected(self):
        recreate = """
        DROP TABLE mijoz;
        CREATE TABLE mijoz (id INT PRIMARY KEY, ism VARCHAR(50) NOT NULL, familiya VARCHAR(50) NOT NULL);
        """
        data = self.check(recreate)
        self.assertFalse(data["is_correct"])
        self.assertIn("«mijoz» jadvalidagi ma'lumotlar kutilganidan farq qiladi", " ".join(data["differences"]))
        self.assertFalse(data["queries"][0]["passed"])

    def test_columns_without_data_fail_queries(self):
        data = self.check("ALTER TABLE mijoz ADD COLUMN ism VARCHAR(50), ADD COLUMN familiya VARCHAR(50);")
        self.assertFalse(data["is_correct"])
        self.assertFalse(all(item["passed"] for item in data["queries"]))

    def test_old_query_breaks_with_clear_message(self):
        data = self.check("ALTER TABLE mijoz RENAME COLUMN fio TO toliq_ism;")
        self.assertFalse(data["is_correct"])
        self.assertIn("Xato berdi", data["queries"][0]["message"])

    def test_hard_coded_values_are_caught_by_hidden_data(self):
        hard_coded = """
        ALTER TABLE mijoz ADD COLUMN ism VARCHAR(50), ADD COLUMN familiya VARCHAR(50);
        UPDATE mijoz SET ism = 'Ali', familiya = 'Valiyev' WHERE id = 1;
        UPDATE mijoz SET ism = 'Laylo', familiya = 'Karimova' WHERE id = 2;
        UPDATE mijoz SET ism = 'Bobur', familiya = 'Valiyev' WHERE id = 3;
        ALTER TABLE mijoz ALTER COLUMN ism SET NOT NULL, ALTER COLUMN familiya SET NOT NULL;
        ALTER TABLE mijoz DROP COLUMN fio;
        """
        data = self.check(hard_coded)
        self.assertFalse(data["is_correct"])
        self.assertTrue(all(item["passed"] for item in data["queries"]))
        self.assertIn("yashirin", data["differences"][0])

    def test_student_sees_queries(self):
        self.auth_as(self.student_a1)
        data = self.client.get(f"/api/labs/{self.evolution_lab.pk}/").data
        self.assertEqual([item["id"] for item in data["check_queries"]], ["royxat", "familiya"])
        self.assertNotIn("solution_sql", data)
        self.assertNotIn("hidden_setup_sql", data)

    def test_teacher_saving_validates_queries(self):
        self.auth_as(self.teacher_a)
        data = {
            "kind": "sql", "title": "Migratsiya", "description": "d", "setup_sql": SETUP, "solution_sql": MIGRATION,
            "hidden_setup_sql": HIDDEN, "check_queries": QUERIES, "groups": [self.group_a.pk],
        }
        response = self.client.post("/api/labs/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        same_before = QUERIES + [{"id": "soni", "title": "Mijozlar soni", "sql": "SELECT count(*) FROM mijoz"}]
        response = self.client.post("/api/labs/", {**data, "check_queries": same_before}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("migratsiyani tekshirmaydi", str(response.data["check_queries"]))

        broken = [{"id": "x", "title": "Yo'q ustun", "sql": "SELECT telefon FROM mijoz"}]
        response = self.client.post("/api/labs/", {**data, "check_queries": broken}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("xato berdi", str(response.data["check_queries"]))

        probes = [{"id": "a", "title": "Hujum", "kind": "attack", "sql": "INSERT INTO mijoz VALUES (7, 'X Y')"}]
        response = self.client.post("/api/labs/", {**data, "hidden_setup_sql": "", "probes": probes}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ReadyEvolutionLabsTests(BaseTestCase):
    def test_ready_labs_are_valid_and_solutions_pass(self):
        from .checker import check_code
        from .evolution import validate_lab_queries
        from .evolution_labs import EVOLUTION_LABS

        for data in EVOLUTION_LABS:
            with self.subTest(lab=data["title"]):
                queries = validate_queries(data["check_queries"])
                validate_lab_queries(data["setup_sql"], data["solution_sql"], data["hidden_setup_sql"], queries)
                lab = Lab(
                    setup_sql=data["setup_sql"], solution_sql=data["solution_sql"],
                    hidden_setup_sql=data["hidden_setup_sql"], check_queries=queries,
                )
                result = check_code(lab, data["solution_sql"])
                self.assertTrue(result["is_correct"], result)
                self.assertTrue(data["theory"].strip())

    def test_typical_mistakes(self):
        from .checker import check_code
        from .evolution_labs import EVOLUTION_LABS

        data = EVOLUTION_LABS[2]
        lab = Lab(setup_sql=data["setup_sql"], solution_sql=data["solution_sql"],
                  hidden_setup_sql=data["hidden_setup_sql"], check_queries=data["check_queries"])
        # trim unutilgan: " +998999990000" bo'sh joy bilan ko'chadi
        no_trim = data["solution_sql"].replace("trim(raqam)", "raqam")
        result = check_code(lab, no_trim)
        self.assertFalse(result["is_correct"])
        self.assertIn("bemor_telefon", " ".join(result["differences"]))
        # Faqat birinchi raqam ko'chirilgan
        first_only = data["solution_sql"].replace(
            "SELECT id, trim(raqam) FROM bemor, unnest(string_to_array(telefonlar, ',')) AS raqam",
            "SELECT id, trim(split_part(telefonlar, ',', 1)) FROM bemor",
        )
        self.assertFalse(check_code(lab, first_only)["is_correct"])
