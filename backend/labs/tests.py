"""Virtual laboratoriya: ruxsatlar, kodni tekshirish va maslahat testlari.

Bu testlar haqiqiy "qum quti" bazasida (LAB_SANDBOX_DB) SQL bajaradi.
"""
import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from ai.client import AITransientError
from users.models import StudentGroup, User

from .checker import HIDDEN_MISMATCH
from .models import BlindReview, Lab, LabAttempt, LabGrade
from .sandbox import run_sql

PASSWORD = "Kuchli-Parol-2026"
SETUP = """
CREATE TABLE kitob (id INT PRIMARY KEY, nomi VARCHAR(100) NOT NULL, narx INT);
INSERT INTO kitob VALUES (1, 'Alifbo', 10), (2, 'Bahor', 30), (3, 'Chaqmoq', 20);
"""
SOLUTION = "SELECT nomi, narx FROM kitob WHERE narx >= 20 ORDER BY narx DESC;"


class BaseTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.group_a = StudentGroup.objects.create(name="A-guruh")
        cls.group_b = StudentGroup.objects.create(name="B-guruh")
        cls.admin = User.objects.create_user("admin1", password=PASSWORD, role=User.Role.ADMIN)
        cls.teacher_a = User.objects.create_user("teacher_a", password=PASSWORD, role=User.Role.TEACHER)
        cls.teacher_b = User.objects.create_user("teacher_b", password=PASSWORD, role=User.Role.TEACHER)
        cls.student_a1 = User.objects.create_user(
            "student_a1", password=PASSWORD, role=User.Role.STUDENT, group=cls.group_a, first_name="Zuhriddin"
        )
        cls.student_a2 = User.objects.create_user(
            "student_a2", password=PASSWORD, role=User.Role.STUDENT, group=cls.group_a
        )
        cls.student_b = User.objects.create_user(
            "student_b", password=PASSWORD, role=User.Role.STUDENT, group=cls.group_b
        )
        cls.group_a.teachers.add(cls.teacher_a)
        cls.group_b.teachers.add(cls.teacher_b)
        cls.lab = Lab.objects.create(
            title="Qimmat kitoblar",
            description="Narxi 20 va undan yuqori kitoblarni narxi kamayish tartibida chiqaring",
            setup_sql=SETUP,
            solution_sql=SOLUTION,
            author=cls.teacher_a,
        )
        cls.lab.groups.add(cls.group_a)
        cls.url = f"/api/labs/{cls.lab.pk}/"
        cls.run_url = f"/api/labs/{cls.lab.pk}/run/"

    def setUp(self):
        cache.clear()

    def auth_as(self, user):
        response = self.client.post("/api/auth/login/", {"username": user.username, "password": PASSWORD})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def run_code(self, sql_code, url=None):
        return self.client.post(url or self.run_url, {"sql_code": sql_code}, format="json")


class SandboxTests(APITestCase):
    """Qum quti talaba kodini cheklab turishini tekshiradi."""

    def test_each_run_starts_clean(self):
        self.assertIsNone(run_sql("CREATE TABLE t (id INT);").error)
        self.assertIsNone(run_sql("CREATE TABLE t (id INT);").error)

    def test_too_much_data_is_stopped(self):
        """Diskni to'ldirish: hajm chegarasidan oshgan kod to'xtatiladi (chegara testda kichraytirilgan)."""
        from . import sandbox

        code = "CREATE TABLE t (s TEXT);" + "INSERT INTO t SELECT repeat('x', 500) FROM generate_series(1, 20000);" * 200
        with patch.object(sandbox, "MAX_STORAGE_BYTES", sandbox._storage_used_now() + 20 * 1024 * 1024):
            outcome = run_sql(code)
        self.assertIn("juda ko'p ma'lumot", outcome.error.message)
        self.assertIsNone(run_sql("SELECT 1").error)

    def test_platform_tables_are_unreachable(self):
        for script in ["SELECT * FROM users_user;", "SELECT * FROM public.users_user;"]:
            self.assertIsNotNone(run_sql(script).error, script)

    def test_cannot_write_outside_own_schema(self):
        outcome = run_sql("COMMIT; CREATE TABLE public.qoldiq (id INT);")
        self.assertEqual(outcome.error.sqlstate, "42501")

    def test_server_internals_are_hidden(self):
        for script in (
            "SELECT datname FROM pg_database;",
            "SELECT rolname FROM pg_roles;",
            "SELECT query FROM pg_stat_activity;",
            "SELECT name, setting FROM pg_settings;",
        ):
            self.assertIn("permission denied", run_sql(script).error.message, script)

    def test_other_databases_are_closed(self):
        from django.db import connection

        main = connection.settings_dict["NAME"]
        outcome = run_sql(f"SELECT has_database_privilege('{main}', 'CONNECT');")
        # Alohida lab_db serverida asosiy baza umuman yo'q; umumiy serverda u yopilgan bo'ladi
        if outcome.error is None:
            self.assertEqual(outcome.result.rows, [("f",)])
        else:
            self.assertIn("does not exist", outcome.error.message)

    def test_temp_file_limit_cannot_be_raised(self):
        outcome = run_sql("SET temp_file_limit = -1;")
        self.assertIn("permission denied", outcome.error.message)
        self.assertEqual(run_sql("SHOW temp_file_limit;").result.rows, [("64MB",)])

    def test_huge_result_is_stopped(self):
        outcome = run_sql("SELECT generate_series(1, 100000000);")
        self.assertIn("juda ko'p qator", outcome.error.message)

    def test_error_reports_line(self):
        outcome = run_sql("SELECT 1;\nSELECT *\nFORM kitob;")
        self.assertEqual(outcome.error.sqlstate, "42601")
        self.assertEqual(outcome.error.line, 3)

    def test_setup_error_is_flagged(self):
        outcome = run_sql("SELECT 1;", "CREATE TABLE x (id INT;")
        self.assertTrue(outcome.setup_failed)


class LabManagementTests(BaseTestCase):
    def payload(self, **overrides):
        data = {
            "title": "Yangi laboratoriya",
            "description": "Barcha kitoblarni chiqaring",
            "setup_sql": SETUP,
            "solution_sql": "SELECT * FROM kitob;",
            "groups": [self.group_a.pk],
        }
        data.update(overrides)
        return data

    def test_teacher_creates_lab(self):
        self.auth_as(self.teacher_a)
        response = self.client.post("/api/labs/", self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["author"]["id"], self.teacher_a.pk)

    def test_broken_solution_is_rejected_with_explanation(self):
        self.auth_as(self.teacher_a)
        response = self.client.post(
            "/api/labs/", self.payload(solution_sql="SELECT * FROM kitoblar;"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("kitoblar", response.data["solution_sql"][0])

    def test_broken_setup_is_rejected(self):
        self.auth_as(self.teacher_a)
        response = self.client.post("/api/labs/", self.payload(setup_sql="CREATE TABLE x (id INT;"), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("setup_sql", response.data)

    def test_teacher_cannot_use_foreign_group(self):
        self.auth_as(self.teacher_a)
        response = self.client.post("/api/labs/", self.payload(groups=[self.group_b.pk]), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_edit_title_without_touching_sql(self):
        self.auth_as(self.teacher_a)
        response = self.client.patch(self.url, {"title": "Yangi nom"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    def test_other_teacher_cannot_see_or_edit(self):
        self.auth_as(self.teacher_b)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.patch(self.url, {"title": "x"}).status_code, status.HTTP_404_NOT_FOUND)

    def test_student_cannot_create_edit_or_delete(self):
        self.auth_as(self.student_a1)
        self.assertEqual(
            self.client.post("/api/labs/", self.payload(), format="json").status_code, status.HTTP_403_FORBIDDEN
        )
        self.assertEqual(self.client.patch(self.url, {"title": "x"}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_removes_attempts(self):
        LabAttempt.objects.create(lab=self.lab, student=self.student_a1, sql_code="SELECT 1", is_correct=False)
        self.auth_as(self.admin)
        self.assertEqual(self.client.delete(self.url).status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(LabAttempt.objects.count(), 0)


class StudentViewTests(BaseTestCase):
    def test_solution_and_groups_are_hidden(self):
        self.auth_as(self.student_a1)
        for data in [self.client.get("/api/labs/").data[0], self.client.get(self.url).data]:
            self.assertNotIn("solution_sql", data)
            self.assertNotIn("groups", data)
            self.assertIn("CREATE TABLE kitob", data["setup_sql"])

    def test_other_group_student_sees_nothing(self):
        self.auth_as(self.student_b)
        self.assertEqual(self.client.get("/api/labs/").data, [])
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.run_code(SOLUTION).status_code, status.HTTP_404_NOT_FOUND)

    def test_progress_follows_own_attempts(self):
        self.auth_as(self.student_a1)
        self.assertEqual(self.client.get(self.url).data["my_progress"], {"attempts": 0, "solved": False, "grade": None, "last_code": ""})
        self.run_code("SELECT nomi FROM kitob;")
        self.run_code(SOLUTION)
        self.assertEqual(
            self.client.get(self.url).data["my_progress"], {"attempts": 2, "solved": True, "grade": None, "last_code": SOLUTION}
        )
        self.assertEqual(self.client.get("/api/labs/").data[0]["my_progress"], {"attempts": 2, "solved": True, "grade": None})
        # Sinfdoshining holatiga ta'sir qilmaydi
        self.auth_as(self.student_a2)
        self.assertEqual(self.client.get("/api/labs/").data[0]["my_progress"], {"attempts": 0, "solved": False, "grade": None})


class RunTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.auth_as(self.student_a1)

    def test_correct_code(self):
        response = self.run_code("select nomi, narx from kitob where narx > 15 order by narx desc")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data["is_correct"])
        self.assertIsNone(response.data["error"])
        self.assertEqual(response.data["result"]["columns"], ["nomi", "narx"])
        self.assertEqual(response.data["result"]["rows"], [["Bahor", "30"], ["Chaqmoq", "20"]])
        self.assertTrue(LabAttempt.objects.get(pk=response.data["attempt_id"]).is_correct)

    def test_syntax_error_gets_tip_and_line(self):
        response = self.run_code("SELECT nomi, narx\nFORM kitob;")
        self.assertFalse(response.data["is_correct"])
        self.assertEqual(response.data["error"]["line"], 2)
        self.assertIn("Sintaksis", response.data["error"]["tip"])
        self.assertFalse(LabAttempt.objects.get().is_correct)

    def test_wrong_rows(self):
        response = self.run_code("SELECT nomi, narx FROM kitob ORDER BY narx DESC;")
        self.assertFalse(response.data["is_correct"])
        self.assertIn("qatorlar soni", response.data["differences"][0])

    def test_wrong_order(self):
        response = self.run_code("SELECT nomi, narx FROM kitob WHERE narx >= 20 ORDER BY narx;")
        self.assertFalse(response.data["is_correct"])
        self.assertIn("tartibi", response.data["differences"][0])

    def test_wrong_columns(self):
        response = self.run_code("SELECT nomi FROM kitob WHERE narx >= 20 ORDER BY narx DESC;")
        self.assertIn("ustunlar soni", response.data["differences"][0])

    def test_no_select_at_the_end(self):
        response = self.run_code("CREATE TEMP TABLE t (id INT);")
        self.assertFalse(response.data["is_correct"])
        self.assertIn("natija qaytarmadi", response.data["differences"][0])

    def test_changing_data_is_noticed(self):
        response = self.run_code("DELETE FROM kitob WHERE id = 1; " + SOLUTION)
        self.assertFalse(response.data["is_correct"])
        self.assertIn("ma'lumotlar", response.data["differences"][0])

    def test_expected_values_are_not_leaked(self):
        response = self.run_code("SELECT nomi, narx + 1 FROM kitob WHERE narx >= 20 ORDER BY narx DESC;")
        self.assertFalse(response.data["is_correct"])
        self.assertNotIn("solution_sql", response.data)
        self.assertNotIn("WHERE narx >= 20", str(response.data["differences"]))

    def test_empty_code_rejected(self):
        self.assertEqual(self.run_code("   ").status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(LabAttempt.objects.count(), 0)

    def test_staff_run_is_not_saved(self):
        self.auth_as(self.teacher_a)
        response = self.run_code(SOLUTION)
        self.assertTrue(response.data["is_correct"])
        self.assertIsNone(response.data["attempt_id"])
        self.assertEqual(LabAttempt.objects.count(), 0)

    def test_anonymous_rejected(self):
        self.client.credentials()
        self.assertEqual(self.run_code(SOLUTION).status_code, status.HTTP_401_UNAUTHORIZED)


class TryRunTests(BaseTestCase):
    """Erkin sinash: natija ko'rsatiladi, lekin tekshirilmaydi va urinish saqlanmaydi."""

    def setUp(self):
        super().setUp()
        self.auth_as(self.student_a1)
        self.try_url = f"/api/labs/{self.lab.pk}/try/"

    def test_shows_result_without_checking_or_saving(self):
        response = self.run_code("SELECT nomi FROM kitob ORDER BY id", url=self.try_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["result"]["rows"], [["Alifbo"], ["Bahor"], ["Chaqmoq"]])
        self.assertIsNone(response.data["error"])
        for key in ("is_correct", "differences", "checked_against_solution", "attempt_id"):
            self.assertNotIn(key, response.data)
        self.assertFalse(LabAttempt.objects.exists())

    def test_solution_is_never_executed(self):
        with patch("labs.checker.run_sql", wraps=run_sql) as runner:
            self.run_code("SELECT 1", url=self.try_url)
        self.assertEqual([call.args[0] for call in runner.call_args_list], ["SELECT 1"])

    def test_shows_tables_after_ddl(self):
        code = "CREATE TABLE muallif (id INT PRIMARY KEY, ism TEXT NOT NULL); INSERT INTO muallif VALUES (1, 'Navoiy');"
        response = self.run_code(code, url=self.try_url)
        tables = {table["name"]: table for table in response.data["tables"]}
        self.assertEqual(set(tables), {"kitob", "muallif"})
        self.assertEqual(
            tables["muallif"]["columns"],
            [{"name": "id", "type": "integer", "not_null": True}, {"name": "ism", "type": "text", "not_null": True}],
        )
        self.assertEqual(tables["muallif"]["row_count"], 1)
        self.assertTrue(any(item.startswith("PRIMARY KEY") for item in tables["muallif"]["constraints"]))
        self.assertIn("INSERT", response.data["status_message"])

    def test_error_gets_tip(self):
        response = self.run_code("SELECT * FROM yoq_jadval", url=self.try_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("jadval topilmadi", response.data["error"]["tip"])
        self.assertFalse(LabAttempt.objects.exists())

    def test_platform_tables_unreachable(self):
        response = self.run_code("SELECT username, password FROM users_user", url=self.try_url)
        self.assertIsNotNone(response.data["error"])
        self.assertIsNone(response.data["result"])

    def test_access_rules(self):
        self.auth_as(self.student_b)  # boshqa guruh talabasi
        self.assertEqual(self.run_code("SELECT 1", url=self.try_url).status_code, status.HTTP_404_NOT_FOUND)
        self.auth_as(self.teacher_a)
        self.assertEqual(self.run_code("SELECT 1", url=self.try_url).status_code, status.HTTP_200_OK)
        self.client.credentials()
        self.assertEqual(self.run_code("SELECT 1", url=self.try_url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_only_sql_labs(self):
        er_lab = Lab.objects.create(kind=Lab.Kind.ER, title="ER", description="ER", author=self.teacher_a)
        er_lab.groups.add(self.group_a)
        response = self.run_code("SELECT 1", url=f"/api/labs/{er_lab.pk}/try/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_code_rejected(self):
        self.assertEqual(self.run_code("", url=self.try_url).status_code, status.HTTP_400_BAD_REQUEST)


class SchemaLabTests(BaseTestCase):
    """Jadval yaratish laboratoriyasi: tuzilish va cheklovlar solishtiriladi."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.schema_lab = Lab.objects.create(
            title="Talabalar jadvali",
            description="guruh va talaba jadvallarini yarating",
            solution_sql=(
                "CREATE TABLE guruh (id SERIAL PRIMARY KEY, nomi VARCHAR(50) NOT NULL UNIQUE);"
                "CREATE TABLE talaba (id SERIAL PRIMARY KEY, ism VARCHAR(100) NOT NULL,"
                " guruh_id INT NOT NULL REFERENCES guruh(id));"
            ),
            author=cls.teacher_a,
        )
        cls.schema_lab.groups.add(cls.group_a)
        cls.schema_url = f"/api/labs/{cls.schema_lab.pk}/run/"

    def setUp(self):
        super().setUp()
        self.auth_as(self.student_a1)

    def test_equivalent_schema_is_correct(self):
        # Boshqacha yozilgan, lekin bir xil tuzilish; ortiqcha CHECK xato emas
        response = self.run_code(
            "CREATE TABLE guruh (id serial, nomi varchar(50) not null, PRIMARY KEY (id), UNIQUE (nomi));"
            "CREATE TABLE talaba (id serial PRIMARY KEY, ism varchar(100) NOT NULL CHECK (ism <> ''),"
            " guruh_id integer NOT NULL, FOREIGN KEY (guruh_id) REFERENCES guruh (id));",
            self.schema_url,
        )
        self.assertTrue(response.data["is_correct"], response.data)

    def test_differences_are_explained(self):
        response = self.run_code(
            "CREATE TABLE guruh (id SERIAL PRIMARY KEY, nomi TEXT);"
            "CREATE TABLE talaba (id SERIAL PRIMARY KEY, ism VARCHAR(100) NOT NULL, guruh_id INT NOT NULL);"
            "CREATE TABLE ortiqcha (id INT);",
            self.schema_url,
        )
        text = " | ".join(response.data["differences"])
        self.assertFalse(response.data["is_correct"])
        self.assertIn("Ortiqcha jadval: «ortiqcha»", text)
        self.assertIn("«guruh.nomi» ustunining turi", text)
        self.assertIn("«guruh» jadvalida UNIQUE cheklovi", text)
        self.assertIn("«talaba» jadvalida FOREIGN KEY cheklovi", text)

    def test_missing_table(self):
        response = self.run_code("CREATE TABLE guruh (id SERIAL PRIMARY KEY, nomi VARCHAR(50) NOT NULL UNIQUE);", self.schema_url)
        self.assertIn("«talaba» jadvali yo'q", " ".join(response.data["differences"]))


class NoSolutionLabTests(BaseTestCase):
    def test_any_working_code_is_correct(self):
        lab = Lab.objects.create(title="Erkin mashq", description="Istalgan jadval yarating", author=self.teacher_a)
        lab.groups.add(self.group_a)
        self.auth_as(self.student_a1)
        url = f"/api/labs/{lab.pk}/run/"
        ok = self.run_code("CREATE TABLE t (id INT); INSERT INTO t VALUES (1); SELECT * FROM t;", url)
        self.assertTrue(ok.data["is_correct"])
        self.assertFalse(ok.data["checked_against_solution"])
        self.assertFalse(self.run_code("CREATE TABLE t (id INT", url).data["is_correct"])


class ProgressTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.auth_as(self.student_a1)
        self.run_code("SELECT 1;")
        self.run_code(SOLUTION)
        self.run_code("SELECT 2;")

    def test_teacher_sees_every_student_of_the_group(self):
        self.auth_as(self.teacher_a)
        response = self.client.get(f"{self.url}progress/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = {row["id"]: row for row in response.data}
        self.assertEqual(set(rows), {self.student_a1.pk, self.student_a2.pk})
        done = rows[self.student_a1.pk]
        self.assertEqual((done["attempts"], done["solved"], done["code"]), (3, True, SOLUTION))
        idle = rows[self.student_a2.pk]
        self.assertEqual((idle["attempts"], idle["solved"], idle["code"]), (0, False, ""))
        self.assertIsNone(idle["last_attempt_at"])

    def test_student_and_other_teacher_denied(self):
        self.assertEqual(self.client.get(f"{self.url}progress/").status_code, status.HTTP_403_FORBIDDEN)
        self.auth_as(self.teacher_b)
        self.assertEqual(self.client.get(f"{self.url}progress/").status_code, status.HTTP_404_NOT_FOUND)


@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="sinov-kaliti")
class AdviceTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.auth_as(self.student_a1)
        response = self.run_code("SELECT nomi FORM kitob;")
        self.assertTrue(response.data["ai_available"])
        self.advice_url = f"/api/labs/attempts/{response.data['attempt_id']}/advice/"

    @patch("labs.views.generate_advice", return_value="FROM so'zini tekshiring.")
    def test_advice_is_saved_and_not_requested_twice(self, generate):
        self.assertEqual(self.client.post(self.advice_url).data["hints"], ["FROM so'zini tekshiring."])
        self.assertEqual(self.client.post(self.advice_url).data["advice"], "FROM so'zini tekshiring.")
        generate.assert_called_once()

    @patch("labs.views.generate_advice", side_effect=["savol", "tushuncha", "ko'rsatma"])
    def test_hint_levels_are_sequential(self, generate):
        first = self.client.post(self.advice_url).data
        self.assertEqual((first["level"], first["max_level"], first["hints"]), (1, 3, ["savol"]))
        self.assertEqual(self.client.post(self.advice_url, {"level": 3}, format="json").status_code, 400)
        second = self.client.post(self.advice_url, {"level": 2}, format="json").data
        self.assertEqual(second["hints"], ["savol", "tushuncha"])
        # 2-daraja uchun AI'ga avvalgi maslahat ham berildi
        self.assertEqual(generate.call_args.args[1:], (2, ["savol"]))
        third = self.client.post(self.advice_url, {"level": 3}, format="json").data
        self.assertEqual(third["advice"], "ko'rsatma")
        self.assertEqual(self.client.post(self.advice_url, {"level": 4}, format="json").status_code, 400)
        attempt = LabAttempt.objects.get(pk=self.advice_url.split("/")[-3])
        self.assertEqual((attempt.ai_hint_level, attempt.ai_advice), (3, "ko'rsatma"))

    @patch("labs.advice.create_message")
    def test_level_instruction_is_sent(self, create_message):
        create_message.return_value.content = [type("Block", (), {"type": "text", "text": "savol"})()]
        self.client.post(self.advice_url)
        message = create_message.call_args.kwargs["messages"][0]["content"]
        self.assertIn("1-daraja", message)
        self.assertNotIn("<oldingi_maslahatlar>", message)

    @patch("labs.advice.create_message")
    def test_solution_and_student_identity_are_not_sent_to_ai(self, create_message):
        create_message.return_value.content = []
        self.client.post(self.advice_url)
        sent = str(create_message.call_args.kwargs)
        self.assertIn("SELECT nomi FORM kitob;", sent)
        self.assertIn("syntax error", sent)
        self.assertNotIn(SOLUTION, sent)
        self.assertNotIn("student_a1", sent)
        self.assertNotIn("Zuhriddin", sent)

    @patch("labs.views.generate_advice", side_effect=AITransientError("tarmoq"))
    def test_ai_failure_does_not_spend_limit(self, generate):
        self.assertEqual(self.client.post(self.advice_url).status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIsNone(LabAttempt.objects.get().ai_requested_at)

    @override_settings(LAB_AI_DAILY_LIMIT=2)
    @patch("labs.views.generate_advice", return_value="Maslahat")
    def test_daily_limit(self, generate):
        # Har bir daraja limitdan alohida yechiladi
        self.assertEqual(self.client.post(self.advice_url).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.post(self.advice_url, {"level": 2}, format="json").status_code, 200)
        second = self.run_code("SELECT nomi FORM kitob;")
        self.assertFalse(second.data["ai_available"])
        response = self.client.post(f"/api/labs/attempts/{second.data['attempt_id']}/advice/")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @patch("labs.views.generate_advice", return_value="Maslahat")
    def test_only_owner_and_only_for_wrong_attempt(self, generate):
        correct = self.run_code(SOLUTION)
        self.assertFalse(correct.data["ai_available"])
        response = self.client.post(f"/api/labs/attempts/{correct.data['attempt_id']}/advice/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.auth_as(self.student_a2)
        self.assertEqual(self.client.post(self.advice_url).status_code, status.HTTP_404_NOT_FOUND)
        self.auth_as(self.teacher_a)
        self.assertEqual(self.client.post(self.advice_url).status_code, status.HTTP_404_NOT_FOUND)
        generate.assert_not_called()


class AdviceNotConfiguredTests(BaseTestCase):
    @override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="")
    def test_run_works_without_ai(self):
        self.auth_as(self.student_a1)
        response = self.run_code("SELECT nomi FORM kitob;")
        self.assertFalse(response.data["ai_available"])
        self.assertIn("Sintaksis", response.data["error"]["tip"])
        advice = self.client.post(f"/api/labs/attempts/{response.data['attempt_id']}/advice/")
        self.assertEqual(advice.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)


class SubmitForGradeTests(BaseTestCase):
    """Baholashga topshirish: AI ishlamasa avtomatik baho, ishlasa AI bahosi."""

    def setUp(self):
        super().setUp()
        self.submit_url = f"{self.url}submit/"
        self.auth_as(self.student_a1)

    def submit(self, sql_code):
        return self.run_code(sql_code, self.submit_url)

    @override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="")
    def test_auto_grade_without_ai(self):
        wrong = self.submit("SELECT nomi FROM kitob;")
        self.assertEqual(wrong.status_code, status.HTTP_200_OK, wrong.data)
        self.assertEqual((wrong.data["grade"]["score"], wrong.data["grade"]["source"]), (0, "auto"))
        right = self.submit(SOLUTION)
        self.assertEqual((right.data["grade"]["score"], right.data["grade"]["source"]), (100, "auto"))
        self.assertTrue(right.data["is_correct"])
        self.assertEqual(LabAttempt.objects.filter(is_submission=True).count(), 2)

    @override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="")
    def test_best_grade_is_kept(self):
        self.submit(SOLUTION)
        worse = self.submit("SELECT 1;")
        self.assertEqual(worse.data["grade"]["score"], 0)
        self.assertEqual(worse.data["best_grade"]["score"], 100)
        grade = LabGrade.objects.get()
        self.assertEqual((grade.score, grade.attempt.sql_code), (100, SOLUTION))
        self.assertEqual(self.client.get(self.url).data["my_progress"]["grade"]["score"], 100)
        self.assertEqual(self.client.get("/api/labs/").data[0]["my_progress"]["grade"]["score"], 100)

    @override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="sinov-kaliti")
    def test_ai_grade_is_clamped_to_check_result(self):
        # AI noto'g'ri kodga yuqori, to'g'ri kodga past ball bersa ham, tekshiruv natijasi ustun
        with patch("labs.advice.create_message") as create_message, patch(
            "labs.advice.extract_text", return_value='{"score": 95, "comment": "Yaxshi urinish"}'
        ):
            wrong = self.submit("SELECT nomi FROM kitob;")
            sent = str(create_message.call_args.kwargs)
        self.assertEqual(wrong.data["grade"], {**wrong.data["grade"], "score": 60, "source": "ai", "comment": "Yaxshi urinish"})
        self.assertNotIn(SOLUTION, sent)
        self.assertNotIn("Zuhriddin", sent)

        with patch("labs.advice.create_message"), patch(
            "labs.advice.extract_text", return_value='{"score": 10, "comment": "Chalkash"}'
        ):
            right = self.submit(SOLUTION)
        self.assertEqual(right.data["grade"]["score"], 70)
        self.assertEqual(right.data["best_grade"]["score"], 70)

    @override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="sinov-kaliti")
    def test_ai_failure_falls_back_to_auto_grade(self):
        for failure in (AITransientError("tarmoq"), None):
            cache.clear()
            with patch("labs.advice.create_message", side_effect=failure), patch(
                "labs.advice.extract_text", return_value="json emas"
            ):
                response = self.submit(SOLUTION)
            self.assertEqual((response.data["grade"]["score"], response.data["grade"]["source"]), (100, "auto"))

    @override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="sinov-kaliti", LAB_AI_GRADES_DAILY_LIMIT=1)
    def test_ai_grades_daily_limit(self):
        with patch("labs.advice.create_message") as create_message, patch(
            "labs.advice.extract_text", return_value='{"score": 90, "comment": "Zo`r"}'
        ):
            self.assertEqual(self.submit(SOLUTION).data["grade"]["source"], "ai")
            self.assertEqual(self.submit(SOLUTION).data["grade"]["source"], "auto")
        create_message.assert_called_once()

    def test_only_student_of_the_group_can_submit(self):
        self.auth_as(self.teacher_a)
        self.assertEqual(self.submit(SOLUTION).status_code, status.HTTP_403_FORBIDDEN)
        self.auth_as(self.student_b)
        self.assertEqual(self.submit(SOLUTION).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(LabGrade.objects.count(), 0)

    @override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="")
    def test_teacher_sees_grades(self):
        self.submit(SOLUTION)
        self.auth_as(self.teacher_a)
        rows = {row["id"]: row for row in self.client.get(f"{self.url}progress/").data}
        self.assertEqual(rows[self.student_a1.pk]["grade"]["score"], 100)
        self.assertIsNone(rows[self.student_a2.pk]["grade"])


class DesignLabsTests(BaseTestCase):
    """Loyihalash bo'yicha tayyor laboratoriyalar (design_labs.py) va ularni qo'shuvchi buyruq."""

    def test_every_solution_passes_its_own_check(self):
        from .checker import check_code
        from .design_labs import DESIGN_LABS

        for lab_data in DESIGN_LABS:
            result = check_code(Lab(**lab_data), lab_data["solution_sql"])
            self.assertTrue(result["is_correct"], (lab_data["title"], result))

    def test_er_labs_accept_their_reference(self):
        from .design_labs import ER_LABS
        from .er import compare, validate_diagram

        for lab_data in ER_LABS:
            reference = validate_diagram(lab_data["reference_diagram"])
            self.assertEqual(compare(reference, reference)["differences"], [], lab_data["title"])
            # Shartda har bir obyekt nomi tilga olingan
            for entity in reference["entities"]:
                self.assertIn(entity["name"], lab_data["description"], lab_data["title"])

    def test_typical_mistakes_are_explained(self):
        from .checker import check_code
        from .design_labs import DESIGN_LABS

        normal_form = Lab(**DESIGN_LABS[3])
        # Telefonlar bo'sh joylari bilan ko'chirilgan: qatorlar soni to'g'ri, qiymatlar xato
        result = check_code(
            normal_form,
            "CREATE TABLE talaba (id INT PRIMARY KEY, ism VARCHAR(100) NOT NULL);"
            "CREATE TABLE talaba_telefon (talaba_id INT NOT NULL REFERENCES talaba(id),"
            " telefon VARCHAR(20) NOT NULL, PRIMARY KEY (talaba_id, telefon));"
            "INSERT INTO talaba SELECT id, ism FROM talaba_eski;"
            "INSERT INTO talaba_telefon SELECT id, unnest(string_to_array(telefonlar, ',')) FROM talaba_eski;",
        )
        self.assertFalse(result["is_correct"])
        self.assertIn("qatorlar soni to'g'ri, lekin ayrim qiymatlar", " ".join(result["differences"]))

        keys = Lab(**DESIGN_LABS[0])
        result = check_code(
            keys,
            "CREATE TABLE kitob (isbn VARCHAR(13), nomi VARCHAR(200) NOT NULL,"
            " muallif VARCHAR(100) NOT NULL, yil INT, sahifalar INT);",
        )
        self.assertIn("«kitob» jadvalida PRIMARY KEY cheklovi yetishmaydi", " ".join(result["differences"]))

    def test_seed_command_is_idempotent(self):
        from io import StringIO

        from django.core.management import call_command
        from django.core.management.base import CommandError

        from .design_labs import DESIGN_LABS

        call_command("seed_design_labs", author="teacher_a", group=["A-guruh"], stdout=StringIO())
        call_command("seed_design_labs", author="teacher_a", group=["A-guruh"], stdout=StringIO())
        labs = Lab.objects.filter(author=self.teacher_a, title__startswith="Loyihalash")
        self.assertEqual(labs.count(), len(DESIGN_LABS))
        self.assertTrue(all(lab.groups.filter(pk=self.group_a.pk).exists() for lab in labs))
        # Ro'yxatda birinchi laboratoriya (ER-model 1) yuqorida turadi
        from .design_labs import ALL_LABS, ER_LABS

        all_labs = Lab.objects.filter(author=self.teacher_a, title__in=[item["title"] for item in ALL_LABS])
        self.assertEqual(all_labs.count(), len(ALL_LABS))
        self.assertEqual(all_labs.order_by("-created_at", "-id").first().title, ALL_LABS[0]["title"])
        self.assertEqual(all_labs.filter(kind="er").count(), len(ER_LABS))

        with self.assertRaises(CommandError):
            call_command("seed_design_labs", author="student_a1", stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command("seed_design_labs", author="teacher_a", group=["Yo'q-guruh"], stdout=StringIO())


class ResearchExportTests(BaseTestCase):
    """Tadqiqot uchun anonim eksport: ruxsatlar, anonimlik va hisoblangan ko'rsatkichlar."""

    export_url = "/api/labs/research-export/"

    def setUp(self):
        super().setUp()
        self.auth_as(self.student_a1)
        self.run_code("SELEC narx FROM kitob;")  # baza xatosi (sintaksis)
        self.run_code("SELECT 1;")  # natija farqli
        self.run_code(SOLUTION)  # to'g'ri
        second = LabAttempt.objects.filter(student=self.student_a1).order_by("id")[1]
        second.ai_advice = "maslahat"
        second.ai_hint_level = 2
        second.save(update_fields=["ai_advice", "ai_hint_level"])
        self.client.credentials()

    def export(self, user, **params):
        import csv
        import io
        import zipfile

        self.auth_as(user)
        response = self.client.get(self.export_url, params)
        if response.status_code != status.HTTP_200_OK:
            return response, None
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        files = {name: archive.read(name).decode("utf-8-sig") for name in archive.namelist()}
        tables = {
            name: list(csv.DictReader(io.StringIO(content), delimiter=";"))
            for name, content in files.items()
            if name.endswith(".csv")
        }
        return response, (files, tables)

    def test_student_cannot_export(self):
        response, _ = self.export(self.student_a1)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_sees_only_own_labs(self):
        _, (_, tables) = self.export(self.teacher_b)
        self.assertEqual(tables["urinishlar.csv"], [])
        _, (_, tables) = self.export(self.teacher_a)
        self.assertEqual(len(tables["urinishlar.csv"]), 3)

    def test_export_is_anonymous(self):
        response, (files, tables) = self.export(self.admin)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertEqual(
            set(files),
            {"urinishlar.csv", "xulosa.csv", "baholash_mosligi.csv", "testlar.csv", "test_javoblari.csv", "README.txt"},
        )
        everything = "".join(files.values())
        for secret in ("student_a1", "Zuhriddin", "SELEC narx", SOLUTION.strip()[:20]):
            self.assertNotIn(secret, everything)
        pseudonyms = {row["talaba"] for row in tables["urinishlar.csv"]}
        self.assertEqual(len(pseudonyms), 1)
        self.assertRegex(pseudonyms.pop(), r"^T-[0-9A-F]{8}$")
        # Taxallus keyingi eksportda ham o'zgarmaydi
        _, (_, again) = self.export(self.admin)
        self.assertEqual(tables["urinishlar.csv"][0]["talaba"], again["urinishlar.csv"][0]["talaba"])

    def test_attempt_rows_and_categories(self):
        _, (_, tables) = self.export(self.teacher_a)
        rows = tables["urinishlar.csv"]
        self.assertEqual([row["urinish_raqami"] for row in rows], ["1", "2", "3"])
        self.assertEqual([row["natija"] for row in rows], ["baza_xatosi", "natija_farqli", "togri"])
        self.assertEqual(rows[0]["xato_turlari"], "sintaksis")
        self.assertEqual(rows[1]["xato_turlari"], "natija_ustunlari_soni")
        self.assertEqual([row["ai_maslahat"] for row in rows], ["0", "1", "0"])
        self.assertEqual([row["maslahat_darajasi"] for row in rows], ["0", "2", "0"])
        self.assertEqual(rows[0]["guruh"], "A-guruh")

    def test_summary_includes_students_who_did_not_start(self):
        _, (_, tables) = self.export(self.teacher_a)
        summary = {row["urinishlar"]: row for row in tables["xulosa.csv"]}
        self.assertEqual(set(summary), {"3", "0"})  # student_a1 va boshlamagan student_a2
        solved = summary["3"]
        self.assertEqual(solved["yechildi"], "1")
        self.assertEqual(solved["togri_gacha_urinishlar"], "3")
        self.assertEqual(solved["baza_xatolari"], "1")
        self.assertEqual(solved["natija_farqlari"], "1")
        self.assertEqual(solved["ai_maslahatlar"], "1")
        self.assertEqual(solved["maslahat_darajalari_jami"], "2")
        self.assertEqual(solved["eng_yuqori_maslahat_darajasi"], "2")
        self.assertEqual(solved["maslahatdan_keyin_yechdi"], "1")
        idle = summary["0"]
        self.assertEqual((idle["yechildi"], idle["maslahatdan_keyin_yechdi"]), ("0", ""))

    def test_old_attempts_without_sqlstate_are_categorized(self):
        from .research import attempt_categories
        from .checker import ERROR_TIPS

        old = LabAttempt(feedback={"error": {"message": "x", "tip": ERROR_TIPS["23505"]}, "differences": []})
        self.assertEqual(attempt_categories(old), ["unique_buzildi"])

    def test_lab_filter(self):
        response, _ = self.export(self.admin, lab="abc")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        _, (_, tables) = self.export(self.admin, lab=str(self.lab.pk + 1000))
        self.assertEqual(tables["urinishlar.csv"], [])


ER_REFERENCE = {
    "entities": [
        {"id": "t", "name": "Talaba", "x": 0, "y": 0, "attributes": [{"name": "id", "key": "pk"}, {"name": "ism"}]},
        {"id": "g", "name": "Guruh", "x": 300, "y": 0, "attributes": [{"name": "id", "key": "pk"}, {"name": "nomi"}]},
        {"id": "f", "name": "Fan", "x": 0, "y": 300, "attributes": [{"name": "id", "key": "pk"}, {"name": "nomi"}]},
    ],
    "relationships": [
        {"id": "r1", "name": "a'zo", "source": "t", "target": "g", "source_card": "N", "target_card": "1"},
        {"id": "r2", "name": "o'qiydi", "source": "t", "target": "f", "source_card": "N", "target_card": "N"},
    ],
}
# Xatolari bor diagramma: Fan yo'q, Talabada PK yo'q, kardinallik teskari
ER_WRONG = {
    "entities": [
        {"id": "1", "name": "talaba", "x": 10, "y": 10, "attributes": [{"name": "ism", "key": ""}]},
        {"id": "2", "name": "Guruh", "x": 200, "y": 10, "attributes": [{"name": "id", "key": "pk"}, {"name": "nomi"}]},
    ],
    "relationships": [{"id": "x", "name": "", "source": "1", "target": "2", "source_card": "1", "target_card": "N"}],
}


# .env dagi haqiqiy kalit testlarda ishlatilmasin: AI faqat mock bilan sinaladi
@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="")
class ErLabTests(BaseTestCase):
    """ER-diagramma laboratoriyasi: tekshirish, maslahat, topshirish va tuzatish."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.er_lab = Lab.objects.create(
            kind=Lab.Kind.ER,
            title="Universitet ER",
            description="Talaba, Guruh va Fan obyektlarini chizing",
            reference_diagram=ER_REFERENCE,
            author=cls.teacher_a,
        )
        cls.er_lab.groups.add(cls.group_a)

    def post(self, action, diagram):
        return self.client.post(f"/api/labs/{self.er_lab.pk}/{action}/", {"diagram": diagram}, format="json")

    def test_reference_is_hidden_from_student(self):
        self.auth_as(self.student_a1)
        response = self.client.get(f"/api/labs/{self.er_lab.pk}/")
        self.assertEqual(response.data["kind"], "er")
        self.assertNotIn("reference_diagram", response.data)
        self.assertNotIn("o'qiydi", str(response.data))

    def test_correct_diagram(self):
        self.auth_as(self.student_a1)
        response = self.post("run", ER_REFERENCE)
        self.assertTrue(response.data["is_correct"], response.data)
        attempt = LabAttempt.objects.get(pk=response.data["attempt_id"])
        self.assertEqual(attempt.diagram["entities"][0]["name"], "Talaba")
        self.assertEqual(attempt.sql_code, "")

    def test_differences_do_not_reveal_answer(self):
        self.auth_as(self.student_a1)
        response = self.post("run", ER_WRONG)
        self.assertFalse(response.data["is_correct"])
        text = " | ".join(response.data["differences"])
        self.assertIn("1 ta obyekt yetishmaydi", text)
        self.assertIn("asosiy kalit (PK) belgilanmagan", text)
        self.assertIn("kardinalligi noto'g'ri (sizda 1:N)", text)
        self.assertNotIn("Fan", text)
        self.assertNotIn("fix", response.data)

    def test_invalid_diagram_rejected(self):
        self.auth_as(self.student_a1)
        bad = {"entities": [{"id": "1", "name": "A"}, {"id": "2", "name": "a"}], "relationships": []}
        response = self.post("run", bad)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ikki marta", str(response.data["diagram"]))
        self.assertEqual(self.post("run", "matn").status_code, status.HTTP_400_BAD_REQUEST)

    def test_submit_wrong_diagram_returns_fix(self):
        self.auth_as(self.student_a1)
        response = self.post("submit", ER_WRONG)
        self.assertEqual(response.data["grade"]["source"], "auto")
        self.assertLessEqual(response.data["grade"]["score"], 60)
        fix = response.data["fix"]
        changes = " | ".join(fix["diagram"]["changes"])
        self.assertIn("«Fan» obyekti qo'shildi", changes)
        self.assertIn("1:N dan N:1 ga", changes)
        statuses = {entity["name"]: entity["status"] for entity in fix["diagram"]["entities"]}
        self.assertEqual(statuses["Fan"], "added")
        # Talaba sahifani qayta ochganda ham tuzatish ko'rinadi
        lab = self.client.get(f"/api/labs/{self.er_lab.pk}/").data
        self.assertEqual(lab["my_progress"]["last_fix"]["diagram"]["changes"], fix["diagram"]["changes"])
        self.assertEqual(lab["my_progress"]["last_diagram"]["entities"][0]["name"], "talaba")

    def test_submit_correct_diagram_has_no_fix(self):
        self.auth_as(self.student_a1)
        response = self.post("submit", ER_REFERENCE)
        self.assertEqual(response.data["grade"]["score"], 100)
        self.assertIsNone(response.data["fix"])

    @override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="sinov-kaliti")
    def test_ai_grade_explains_fix_without_identity(self):
        reply = {"score": 95, "comment": "izoh", "fix_explanation": "- Fan kerak, chunki ..."}
        with patch("labs.advice.create_message") as create_message:
            create_message.return_value.content = [type("Block", (), {"type": "text", "text": json.dumps(reply)})()]
            self.auth_as(self.student_a1)
            response = self.post("submit", ER_WRONG)
        self.assertEqual(response.data["grade"]["source"], "ai")
        self.assertEqual(response.data["grade"]["score"], 60)  # noto'g'ri diagramma 60 dan oshmaydi
        self.assertEqual(response.data["fix"]["explanation"], "- Fan kerak, chunki ...")
        payload = json.dumps(create_message.call_args.kwargs, ensure_ascii=False)
        self.assertIn("«Fan» obyekti qo'shildi", payload)
        for secret in ("student_a1", "Zuhriddin"):
            self.assertNotIn(secret, payload)

    @override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="sinov-kaliti")
    def test_advice_does_not_send_reference(self):
        self.auth_as(self.student_a1)
        attempt_id = self.post("run", ER_WRONG).data["attempt_id"]
        with patch("labs.advice.create_message") as create_message:
            create_message.return_value.content = [type("Block", (), {"type": "text", "text": "maslahat"})()]
            response = self.client.post(f"/api/labs/attempts/{attempt_id}/advice/")
        self.assertEqual(response.data["advice"], "maslahat")
        kwargs = create_message.call_args.kwargs
        self.assertIn("ER-diagramma", kwargs["system"])
        message = kwargs["messages"][0]["content"]
        # Namunadagi obyekt (Fan) va bog'lanish nomi (o'qiydi) AI'ga yuborilmaydi
        self.assertNotIn("Fan", message.replace("Fan obyektlarini", ""))
        self.assertNotIn("o'qiydi", message)

    def test_explanation_bullets_are_split(self):
        from .advice import split_bullets

        self.assertEqual(split_bullets("- Bir. - Ikki: a - b. - Uch!"), "- Bir.\n- Ikki: a - b.\n- Uch!")

    def test_teacher_creates_er_lab_and_kind_is_fixed(self):
        self.auth_as(self.teacher_a)
        data = {"kind": "er", "title": "ER", "description": "shart", "groups": [self.group_a.pk]}
        response = self.client.post("/api/labs/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reference_diagram", response.data)

        data["reference_diagram"] = ER_REFERENCE
        data["solution_sql"] = "SELECT 1;"
        response = self.client.post("/api/labs/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["solution_sql"], "")
        response = self.client.patch(f"/api/labs/{response.data['id']}/", {"kind": "sql"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_progress_and_export_include_er(self):
        self.auth_as(self.student_a1)
        self.post("run", ER_WRONG)
        self.auth_as(self.teacher_a)
        rows = self.client.get(f"/api/labs/{self.er_lab.pk}/progress/").data
        mine = next(row for row in rows if row["id"] == self.student_a1.pk)
        self.assertEqual(mine["diagram"]["entities"][1]["name"], "Guruh")

        import csv
        import io
        import zipfile

        archive = zipfile.ZipFile(io.BytesIO(self.client.get("/api/labs/research-export/").content))
        rows = list(csv.DictReader(io.StringIO(archive.read("urinishlar.csv").decode("utf-8-sig")), delimiter=";"))
        er_rows = [row for row in rows if row["laboratoriya_turi"] == "er"]
        self.assertEqual(len(er_rows), 1)
        self.assertIn("er_obyekt_yetishmaydi", er_rows[0]["xato_turlari"])
        self.assertIn("er_kardinallik", er_rows[0]["xato_turlari"])


@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="sinov-kaliti")
class AiDisabledGroupTests(BaseTestCase):
    """Tajriba: nazorat guruhida AI talabaga hech qayerda ko'rinmaydi (kalit sozlangan bo'lsa ham)."""

    def setUp(self):
        super().setUp()
        self.group_a.ai_enabled = False
        self.group_a.save(update_fields=["ai_enabled"])
        self.auth_as(self.student_a1)

    def test_me_reports_ai_disabled(self):
        self.assertFalse(self.client.get("/api/auth/me/").data["ai_enabled"])
        self.auth_as(self.teacher_a)
        self.assertTrue(self.client.get("/api/auth/me/").data["ai_enabled"])

    def test_lab_advice_and_ai_grade_are_off(self):
        with patch("labs.advice.create_message") as create_message:
            run = self.run_code("SELECT 1;")
            self.assertFalse(run.data["ai_available"])
            response = self.client.post(f"/api/labs/attempts/{run.data['attempt_id']}/advice/")
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
            submit = self.client.post(f"/api/labs/{self.lab.pk}/submit/", {"sql_code": SOLUTION}, format="json")
            self.assertEqual(submit.data["grade"]["source"], "auto")
        create_message.assert_not_called()
        self.assertFalse(LabAttempt.objects.filter(student=self.student_a1).first().ai_enabled)

    def test_er_fix_has_no_ai_explanation(self):
        lab = Lab.objects.create(
            kind=Lab.Kind.ER, title="ER", description="d", reference_diagram=ER_REFERENCE, author=self.teacher_a
        )
        lab.groups.add(self.group_a)
        with patch("labs.advice.create_message") as create_message:
            response = self.client.post(f"/api/labs/{lab.pk}/submit/", {"diagram": ER_WRONG}, format="json")
        create_message.assert_not_called()
        # Tuzatilgan diagramma (AI emas, tizim quradi) ko'rsatiladi, AI tushuntirishi yo'q
        self.assertTrue(response.data["fix"]["diagram"]["changes"])
        self.assertEqual(response.data["fix"]["explanation"], "")

    def test_assignment_chat_and_analysis_are_closed(self):
        from datetime import timedelta

        from django.utils import timezone

        from learning.models import Assignment
        from submissions.models import Submission

        assignment = Assignment.objects.create(
            title="T", description="d", author=self.teacher_a, deadline=timezone.now() + timedelta(days=1)
        )
        assignment.groups.add(self.group_a)
        submission = Submission.objects.create(
            assignment=assignment, student=self.student_a1, sql_code="SELECT 1;", attempt_number=1
        )
        self.assertEqual(self.client.get(f"/api/assignments/{assignment.pk}/chat/").status_code, 403)
        self.assertEqual(
            self.client.post(f"/api/assignments/{assignment.pk}/chat/", {"content": "savol"}).status_code, 403
        )
        self.assertEqual(self.client.get(f"/api/submissions/{submission.pk}/analysis/").status_code, 403)
        # O'qituvchi tahlilni ko'raveradi
        self.auth_as(self.teacher_a)
        self.assertNotEqual(self.client.get(f"/api/submissions/{submission.pk}/analysis/").status_code, 403)

    def test_export_marks_control_group(self):
        import csv
        import io
        import zipfile

        self.run_code("SELECT 1;")
        self.group_a.ai_enabled = True  # keyin yoqilsa ham, urinish paytidagi holat saqlanadi
        self.group_a.save(update_fields=["ai_enabled"])
        self.auth_as(self.teacher_a)
        archive = zipfile.ZipFile(io.BytesIO(self.client.get("/api/labs/research-export/").content))
        read = lambda name: list(  # noqa: E731
            csv.DictReader(io.StringIO(archive.read(name).decode("utf-8-sig")), delimiter=";")
        )
        self.assertEqual(read("urinishlar.csv")[0]["ai_yoqilgan"], "0")
        self.assertEqual({row["ai_yoqilgan"] for row in read("xulosa.csv")}, {"1"})

    def test_admin_toggles_group_ai(self):
        self.auth_as(self.admin)
        response = self.client.patch(f"/api/groups/{self.group_a.pk}/", {"ai_enabled": True}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["ai_enabled"])
        self.auth_as(self.teacher_a)
        response = self.client.patch(f"/api/groups/{self.group_a.pk}/", {"ai_enabled": False}, format="json")
        self.assertIn(response.status_code, (403, 404))


class StatisticsTests(BaseTestCase):
    stats_url = "/api/statistics/"

    def test_numbers(self):
        self.auth_as(self.student_a1)
        self.run_code("SELEC 1;")  # sintaksis
        wrong = self.run_code("SELECT 1;").data["attempt_id"]
        LabAttempt.objects.filter(pk=wrong).update(ai_advice="maslahat")
        self.run_code(SOLUTION)  # maslahatdan keyin yechdi
        self.auth_as(self.student_a2)
        self.run_code("SELECT 1;")  # yechmadi, maslahatsiz

        self.auth_as(self.teacher_a)
        data = self.client.get(self.stats_url).data
        self.assertEqual(data["overview"]["students"], 2)
        self.assertEqual(data["overview"]["attempts"], 4)
        self.assertEqual(data["overview"]["solved_rate"], 50.0)
        categories = {item["category"]: item["count"] for item in data["top_errors"]}
        self.assertEqual(categories["sintaksis"], 1)
        self.assertEqual(categories["natija_ustunlari_soni"], 2)
        lab = data["labs"][0]
        self.assertEqual((lab["students"], lab["solved"], lab["attempts_to_solve"]), (2, 1, 3.0))
        self.assertEqual(data["ai_effect"]["with_advice"], {"pairs": 1, "solved": 1, "rate": 100.0})
        self.assertEqual(data["ai_effect"]["without_advice"], {"pairs": 1, "solved": 0, "rate": 0.0})
        self.assertEqual([group["name"] for group in data["groups"]], ["A-guruh"])

    def test_permissions_and_group_filter(self):
        self.auth_as(self.student_a1)
        self.assertEqual(self.client.get(self.stats_url).status_code, 403)
        self.auth_as(self.teacher_a)
        self.assertEqual(self.client.get(self.stats_url, {"group": self.group_b.pk}).status_code, 404)
        self.assertEqual(self.client.get(self.stats_url, {"group": "x"}).status_code, 400)
        self.assertEqual(self.client.get(self.stats_url, {"group": self.group_a.pk}).data["overview"]["students"], 2)
        # Boshqa o'qituvchi A-guruh laboratoriyasini ko'rmaydi
        self.auth_as(self.teacher_b)
        self.assertEqual(self.client.get(self.stats_url).data["overview"]["labs"], 0)
        self.auth_as(self.admin)
        self.assertEqual(len(self.client.get(self.stats_url).data["groups_available"]), 2)


class LearningCurveTests(BaseTestCase):
    stats_url = "/api/statistics/"

    def test_labs_follow_learning_order_and_split_by_ai(self):
        from datetime import timedelta

        from django.utils import timezone

        # Seed buyrug'idagidek: 1-laboratoriya oxirida yaratiladi
        second = self.lab
        first = Lab.objects.create(title="Birinchi", setup_sql=SETUP, solution_sql=SOLUTION, author=self.teacher_a)
        unstarted_old = Lab.objects.create(title="Boshlanmagan eski", setup_sql=SETUP, solution_sql=SOLUTION, author=self.teacher_a)
        unstarted_new = Lab.objects.create(title="Boshlanmagan yangi", setup_sql=SETUP, solution_sql=SOLUTION, author=self.teacher_a)
        for lab in (first, unstarted_old, unstarted_new):
            lab.groups.add(self.group_a)
        Lab.objects.filter(pk=unstarted_new.pk).update(created_at=timezone.now() + timedelta(minutes=1))
        control = StudentGroup.objects.create(name="Nazorat", ai_enabled=False)
        control.teachers.add(self.teacher_a)
        for lab in (first, second):
            lab.groups.add(control)
        control_student = User.objects.create_user("control1", password=PASSWORD, role=User.Role.STUDENT, group=control)

        start = timezone.now() - timedelta(days=7)

        def attempt(lab, student, correct, days):
            item = LabAttempt.objects.create(lab=lab, student=student, is_correct=correct)
            LabAttempt.objects.filter(pk=item.pk).update(created_at=start + timedelta(days=days))

        attempt(first, self.student_a1, False, 0)
        attempt(first, self.student_a1, True, 0.1)  # AI guruhi: 2 urinishda
        attempt(first, control_student, True, 0.2)  # nazorat: 1 urinishda
        attempt(second, self.student_a1, True, 2)
        attempt(second, control_student, False, 2)
        attempt(second, control_student, False, 2.1)
        attempt(second, control_student, True, 2.2)  # nazorat: 3 urinishda

        self.auth_as(self.teacher_a)
        data = self.client.get(self.stats_url).data
        self.assertEqual(
            [lab["title"] for lab in data["labs"]],
            ["Birinchi", second.title, "Boshlanmagan yangi", "Boshlanmagan eski"],
        )
        curve = data["learning_curve"]
        self.assertEqual([point["position"] for point in curve], [1, 2, 3, 4])
        self.assertEqual(curve[0]["ai"], {"students": 2, "solved": 1, "attempts_to_solve": 2.0, "first_try_rate": 0.0})
        self.assertEqual(curve[0]["control"]["attempts_to_solve"], 1.0)
        self.assertEqual(curve[1]["control"]["attempts_to_solve"], 3.0)
        self.assertEqual(curve[1]["ai"]["first_try_rate"], 50.0)
        self.assertIsNone(curve[3]["ai"]["attempts_to_solve"])


class DuplicateLabTests(BaseTestCase):
    def test_teacher_duplicates_own_lab(self):
        Lab.objects.filter(pk=self.lab.pk).update(theory="Nazariya matni")
        self.lab.refresh_from_db()
        LabAttempt.objects.create(lab=self.lab, student=self.student_a1, sql_code="x", is_correct=False)
        self.auth_as(self.teacher_a)
        response = self.client.post(f"/api/labs/{self.lab.pk}/duplicate/")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        copy = Lab.objects.get(pk=response.data["id"])
        self.assertEqual(copy.title, "Qimmat kitoblar (nusxa)")
        self.assertEqual((copy.setup_sql, copy.solution_sql), (self.lab.setup_sql, self.lab.solution_sql))
        self.assertEqual(copy.theory, "Nazariya matni")
        self.assertEqual(list(copy.groups.all()), [self.group_a])
        self.assertEqual(copy.attempts.count(), 0)

    def test_others_cannot_duplicate(self):
        self.auth_as(self.student_a1)
        self.assertEqual(self.client.post(f"/api/labs/{self.lab.pk}/duplicate/").status_code, 403)
        self.auth_as(self.teacher_b)
        self.assertEqual(self.client.post(f"/api/labs/{self.lab.pk}/duplicate/").status_code, 404)


class BlindReviewTests(BaseTestCase):
    """Ko'r baholash: ish ism va AI bahosisiz beriladi, baho bir marta qo'yiladi, moslik to'g'ri hisoblanadi."""

    review_url = "/api/labs/blind-review/"

    def setUp(self):
        super().setUp()
        self.grades = []
        for student, score, source in ((self.student_a1, 90, "ai"), (self.student_a2, 40, "auto")):
            attempt = LabAttempt.objects.create(
                lab=self.lab, student=student, sql_code=f"SELECT {score};", is_correct=score > 50,
                feedback={"differences": ["Natijadagi qatorlar soni farq qiladi"]}, is_submission=True,
            )
            self.grades.append(
                LabGrade.objects.create(
                    lab=self.lab, student=student, attempt=attempt, score=score, source=source,
                    comment="MAXFIY-AI-IZOH",
                )
            )

    def auth_as(self, user):
        cache.clear()  # login cheklovi xalaqit bermasin
        super().auth_as(user)

    def review(self, attempt_id, score):
        return self.client.post(self.review_url, {"attempt": attempt_id, "score": score}, format="json")

    def test_student_cannot_review(self):
        self.auth_as(self.student_a1)
        self.assertEqual(self.client.get(self.review_url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.review(self.grades[0].attempt_id, 100).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(self.review_url + "agreement/").status_code, status.HTTP_403_FORBIDDEN)

    def test_item_hides_student_and_system_grade(self):
        self.auth_as(self.teacher_a)
        data = self.client.get(self.review_url).data
        self.assertEqual((data["remaining"], data["reviewed"]), (2, 0))
        text = str(data)
        for secret in ("MAXFIY-AI-IZOH", "Zuhriddin", "student_a", "'score'", "source", str(self.student_a1.pk) + ","):
            self.assertNotIn(secret, text)
        self.assertIn(data["item"]["code"], {"SELECT 90;", "SELECT 40;"})
        self.assertEqual(data["item"]["check"]["differences"], ["Natijadagi qatorlar soni farq qiladi"])

    def test_review_is_saved_once_with_snapshot(self):
        self.auth_as(self.teacher_a)
        attempt_id = self.grades[0].attempt_id
        self.assertEqual(self.review(attempt_id, 70).status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.review(attempt_id, 95).status_code, status.HTTP_409_CONFLICT)
        review = BlindReview.objects.get()
        self.assertEqual((review.score, review.ai_score, review.ai_source), (70, 90, "ai"))
        # Talaba keyin qayta topshirib, bahosi o'zgarsa ham juftlik o'zgarmaydi
        LabGrade.objects.filter(pk=self.grades[0].pk).update(score=100)
        review.refresh_from_db()
        self.assertEqual(review.ai_score, 90)
        data = self.client.get(self.review_url).data
        self.assertEqual((data["remaining"], data["reviewed"]), (1, 1))
        self.assertEqual(data["item"]["attempt_id"], self.grades[1].attempt_id)

    def test_invalid_input(self):
        self.auth_as(self.teacher_a)
        attempt_id = self.grades[0].attempt_id
        for score in (101, -1, "80", True, 7.5, None):
            self.assertEqual(self.review(attempt_id, score).status_code, status.HTTP_400_BAD_REQUEST, score)
        self.assertEqual(self.review(str(attempt_id), 50).status_code, status.HTTP_400_BAD_REQUEST)
        # Baholanmagan (navbatda yo'q) urinish
        other = LabAttempt.objects.create(lab=self.lab, student=self.student_a1, is_correct=False)
        self.assertEqual(self.review(other.pk, 50).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(self.review_url, {"lab": "1 OR 1=1"}).status_code, 400)
        self.assertFalse(BlindReview.objects.exists())

    def test_other_teacher_cannot_see_or_review(self):
        self.auth_as(self.teacher_b)
        data = self.client.get(self.review_url).data
        self.assertEqual((data["item"], data["remaining"]), (None, 0))
        self.assertEqual(self.review(self.grades[0].attempt_id, 50).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(BlindReview.objects.exists())

    def test_agreement_visibility_and_export(self):
        import csv
        import io
        import zipfile

        self.auth_as(self.teacher_a)
        self.review(self.grades[0].attempt_id, 80)
        self.auth_as(self.admin)
        self.review(self.grades[1].attempt_id, 45)

        # O'qituvchi faqat o'zi baholagan ishlar juftligini ko'radi, admin — hammasini
        self.auth_as(self.teacher_a)
        mine = self.client.get(self.review_url + "agreement/").data
        self.assertEqual(mine["overall"]["count"], 1)
        self.assertEqual(mine["pairs"], [{"lab_id": self.lab.pk, "lab_kind": "sql", "system": 90, "teacher": 80, "source": "ai"}])
        self.auth_as(self.admin)
        everything = self.client.get(self.review_url + "agreement/").data
        self.assertEqual(everything["overall"]["count"], 2)
        self.assertEqual(everything["overall"]["mean_diff"], 2.5)  # (10 + -5) / 2
        self.assertEqual(everything["by_source"]["auto"]["count"], 1)

        archive = zipfile.ZipFile(io.BytesIO(self.client.get("/api/labs/research-export/").content))
        rows = list(csv.DictReader(io.StringIO(archive.read("baholash_mosligi.csv").decode("utf-8-sig")), delimiter=";"))
        self.assertEqual([(row["tizim_ball"], row["oqituvchi_ball"], row["farq"]) for row in rows], [("90", "80", "10"), ("40", "45", "-5")])
        self.assertEqual([(row["tizim_baho"], row["oqituvchi_baho"]) for row in rows], [("5", "4"), ("2", "2")])
        self.assertTrue(all(row["baholovchi"].startswith("O-") for row in rows))
        self.assertNotIn("teacher_a", archive.read("baholash_mosligi.csv").decode("utf-8-sig"))


class AgreementMathTests(TestCase):
    def test_statistics(self):
        from .blind_review import agreement_stats, band, pearson, weighted_kappa

        self.assertEqual([band(score) for score in (100, 86, 85, 71, 70, 55, 54, 0)], [5, 5, 4, 4, 3, 3, 2, 2])
        self.assertAlmostEqual(pearson([1, 2, 3], [2, 4, 6]), 1.0)
        self.assertIsNone(pearson([5, 5], [1, 2]))
        self.assertEqual(weighted_kappa([2, 3, 4, 5], [2, 3, 4, 5]), 1.0)
        # Qarama-qarshi baholar — manfiy kappa
        self.assertLess(weighted_kappa([2, 2, 5, 5], [5, 5, 2, 2]), 0)

        class Review:
            def __init__(self, ai_score, score):
                self.ai_score, self.score = ai_score, score

        stats = agreement_stats([Review(90, 80), Review(60, 60), Review(30, 50)])
        self.assertEqual(stats["count"], 3)
        self.assertEqual(stats["mean_abs_diff"], 10.0)
        self.assertEqual(stats["mean_diff"], -3.3)
        self.assertEqual(stats["band_agreement"], 0.667)
        self.assertEqual(stats["within_10"], 0.667)
        self.assertEqual(agreement_stats([]), {"count": 0})


COPIED_SQL = """-- kitoblarni narx bo'yicha saralaymiz
SELECT nomi AS kitob_nomi, narx AS bahosi
FROM kitob k
WHERE k.narx >= 20
ORDER BY bahosi DESC;"""
OWN_SQL = """select nomi, narx from kitob where narx between 20 and 1000000 order by 2 desc"""


class SimilarityTests(BaseTestCase):
    """Ko'chirishni aniqlash: talabaning o'z tanlovlari solishtiriladi, namunaga mos qismlar emas."""

    def setUp(self):
        super().setUp()
        self.student_a3 = User.objects.create_user(
            "student_a3", password=PASSWORD, role=User.Role.STUDENT, group=self.group_a
        )
        self.url = f"/api/labs/{self.lab.pk}/similarity/"

    def attempt(self, student, code, correct=True, diagram=None, lab=None):
        return LabAttempt.objects.create(
            lab=lab or self.lab, student=student, sql_code=code, diagram=diagram, is_correct=correct
        )

    def get(self, user=None):
        self.auth_as(user or self.teacher_a)
        return self.client.get(self.url)

    def test_copied_solution_is_flagged_but_independent_ones_are_not(self):
        self.attempt(self.student_a1, COPIED_SQL)
        self.attempt(self.student_a2, COPIED_SQL.replace("DESC;", "DESC ;"))  # bo'sh joy farqi
        self.attempt(self.student_a3, OWN_SQL)
        data = self.get().data
        self.assertEqual(len(data["pairs"]), 1)
        pair = data["pairs"][0]
        self.assertEqual({student["id"] for student in pair["students"]}, {self.student_a1.pk, self.student_a2.pk})
        self.assertEqual(pair["score"], 1.0)
        self.assertIsNotNone(pair["gap_minutes"])

    def test_solutions_equal_to_reference_are_not_flagged(self):
        for student in (self.student_a1, self.student_a2):
            self.attempt(student, SOLUTION)
        self.assertEqual(self.get().data["pairs"], [])

    def test_shared_unusual_wrong_attempt_is_flagged(self):
        wrong = "SELECT nomi, narx, muallif FROM kitob WHERE narx > 20 AND nomi LIKE '%a%' ORDER BY nomi;"
        self.attempt(self.student_a1, wrong, correct=False)
        self.attempt(self.student_a2, wrong, correct=False)
        self.attempt(self.student_a1, SOLUTION)
        self.attempt(self.student_a2, OWN_SQL)
        pairs = self.get().data["pairs"]
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["shared_wrong"], 1)

    def test_er_names_are_compared(self):
        reference = {
            "entities": [{"id": "e1", "name": "Talaba", "x": 0, "y": 0, "attributes": [{"name": "id", "key": "pk"}]}],
            "relationships": [],
        }
        lab = Lab.objects.create(kind="er", title="ER", reference_diagram=reference, author=self.teacher_a)
        lab.groups.add(self.group_a)

        def diagram(*names):
            return {
                "entities": [
                    {"id": "e1", "name": "Talaba", "x": 0, "y": 0,
                     "attributes": [{"name": "id", "key": "pk"}] + [{"name": name, "key": ""} for name in names]},
                    {"id": "e2", "name": "Yotoqxona xonasi", "x": 0, "y": 0, "attributes": [{"name": "qavat", "key": ""}]},
                ],
                "relationships": [],
            }

        unusual = ("tugilgan_joyi", "sevimli_fan", "oyoq_kiyim_olchami", "telefon_2")
        self.attempt(self.student_a1, "", False, diagram(*unusual), lab)
        self.attempt(self.student_a2, "", False, diagram(*[name.upper() for name in unusual]), lab)
        self.attempt(self.student_a3, "", False, diagram("ism", "familiya", "manzil", "telefon"), lab)
        self.url = f"/api/labs/{lab.pk}/similarity/"
        pairs = self.get().data["pairs"]
        self.assertEqual(len(pairs), 1)
        self.assertEqual({student["id"] for student in pairs[0]["students"]}, {self.student_a1.pk, self.student_a2.pk})

    def test_access(self):
        self.attempt(self.student_a1, COPIED_SQL)
        self.attempt(self.student_a2, COPIED_SQL)
        self.assertEqual(self.get(self.student_a1).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.get(self.teacher_b).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.get(self.admin).status_code, status.HTTP_200_OK)


class TheoryTests(BaseTestCase):
    """Nazariya va namuna: talabaga ko'rinadi, yechimni bermaydi."""

    def test_student_sees_theory_but_not_solution(self):
        Lab.objects.filter(pk=self.lab.pk).update(theory="WHERE qatorlarni filtrlaydi")
        self.auth_as(self.student_a1)
        data = self.client.get(self.url).data
        self.assertEqual(data["theory"], "WHERE qatorlarni filtrlaydi")
        self.assertNotIn("solution_sql", data)

    def test_teacher_edits_theory_with_length_limit(self):
        self.auth_as(self.teacher_a)
        response = self.client.patch(self.url, {"theory": "Yangi nazariya"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.lab.refresh_from_db()
        self.assertEqual(self.lab.theory, "Yangi nazariya")
        response = self.client.patch(self.url, {"theory": "x" * 20_001}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.auth_as(self.student_a1)
        self.assertEqual(self.client.patch(self.url, {"theory": "x"}, format="json").status_code, 403)

    def test_every_ready_lab_has_theory(self):
        from .design_labs import ALL_LABS

        for lab_data in ALL_LABS:
            self.assertTrue(lab_data["theory"].strip(), lab_data["title"])

    def test_examples_do_not_reveal_solutions(self):
        """Namunada laboratoriya yechimidagi jadvallar yaratilmaydi: misol boshqa mavzuda bo'lishi kerak."""
        import re

        from .design_labs import DESIGN_LABS

        for lab_data in DESIGN_LABS:
            solution_tables = set(re.findall(r"CREATE TABLE (\w+)", lab_data["solution_sql"], re.IGNORECASE))
            example_tables = set(re.findall(r"CREATE TABLE (\w+)", lab_data["theory"], re.IGNORECASE))
            self.assertFalse(solution_tables & example_tables, lab_data["title"])
            self.assertNotIn(lab_data["solution_sql"].strip(), lab_data["theory"])

    def test_examples_run_in_sandbox(self):
        import re

        from .design_labs import DESIGN_LABS

        helpers = (
            "CREATE TABLE film (id INT PRIMARY KEY); CREATE TABLE aktyor (id INT PRIMARY KEY);"
            "INSERT INTO film VALUES (1), (2); INSERT INTO aktyor VALUES (2), (3);"
            "CREATE TABLE seans (id INT PRIMARY KEY); CREATE TABLE xona (id INT PRIMARY KEY);"
            "CREATE TABLE mehmon (id INT PRIMARY KEY);"
            "CREATE TABLE dars (talaba_id INT, fan_kodi VARCHAR(10), fan_nomi VARCHAR(100), baho INT);"
            "INSERT INTO dars VALUES (1, 'F1', 'Fizika', 5), (2, 'F1', 'Fizika', 4);"
        )
        for lab_data in DESIGN_LABS:
            for code in re.findall(r"```sql\n(.*?)```", lab_data["theory"], re.DOTALL):
                self.assertIsNone(run_sql(code, helpers).error, lab_data["title"])

    def test_migration_fills_only_empty_theory(self):
        import importlib

        from django.apps import apps

        from .theory import THEORY

        title = next(iter(THEORY))
        empty = Lab.objects.create(title=title, description="d", author=self.teacher_a)
        custom = Lab.objects.create(title=title, description="d", theory="O'qituvchi matni", author=self.teacher_a)
        importlib.import_module("labs.migrations.0008_tayyor_nazariya").fill_theory(apps, None)
        empty.refresh_from_db()
        custom.refresh_from_db()
        self.assertEqual(empty.theory, THEORY[title])
        self.assertEqual(custom.theory, "O'qituvchi matni")


HIDDEN_SETUP = """
CREATE TABLE kitob (id INT PRIMARY KEY, nomi VARCHAR(100) NOT NULL, narx INT);
INSERT INTO kitob VALUES (4, 'Yashirin-Dengiz', 50), (5, 'Yashirin-Tog', 15), (6, 'Yashirin-Osmon', 25);
"""
# Ko'rinadigan ma'lumotlardagi to'g'ri natijani qo'lda yozish
HARDCODED = "SELECT 'Bahor' AS nomi, 30 AS narx UNION ALL SELECT 'Chaqmoq', 20 ORDER BY narx DESC;"


class HiddenDataTests(BaseTestCase):
    """Yashirin test ma'lumotlari: natijani qo'lda yozib aldab bo'lmaydi va yashirin ma'lumot sir qoladi."""

    def setUp(self):
        super().setUp()
        Lab.objects.filter(pk=self.lab.pk).update(hidden_setup_sql=HIDDEN_SETUP)
        self.auth_as(self.student_a1)

    def assert_no_hidden_leak(self, response):
        text = json.dumps(response.data, default=str)
        self.assertNotIn("Yashirin", text)
        self.assertNotIn("hidden_setup_sql", text)

    def test_hardcoded_result_fails(self):
        response = self.run_code(HARDCODED)
        self.assertFalse(response.data["is_correct"])
        self.assertIsNone(response.data["error"])
        self.assertEqual(response.data["differences"], [HIDDEN_MISMATCH])
        # Ko'rinadigan natija talabaga ko'rsatiladi, yashirini emas
        self.assertEqual(response.data["result"]["rows"], [["Bahor", "30"], ["Chaqmoq", "20"]])
        self.assert_no_hidden_leak(response)
        self.assertFalse(LabAttempt.objects.get().is_correct)

    def test_real_query_passes(self):
        response = self.run_code("SELECT nomi, narx FROM kitob WHERE narx >= 20 ORDER BY narx DESC")
        self.assertTrue(response.data["is_correct"], response.data)

    def test_error_only_on_hidden_data_reveals_nothing(self):
        # id=4 faqat yashirin ma'lumotda bor; xato matni yashirin qiymatni o'z ichiga oladi:
        # invalid input syntax for type integer: "Yashirin-Dengiz" — u talabaga ko'rsatilmasligi kerak
        code = (
            "SELECT nomi, narx FROM kitob WHERE narx >= 20 "
            "AND (CASE WHEN id = 4 THEN nomi::int ELSE 0 END) = 0 ORDER BY narx DESC"
        )
        response = self.run_code(code)
        self.assertFalse(response.data["is_correct"])
        self.assertIsNone(response.data["error"])
        self.assertEqual(response.data["differences"], [HIDDEN_MISMATCH])
        self.assert_no_hidden_leak(response)

    def test_submit_is_graded_with_hidden_data(self):
        with patch("labs.views.ai_usable", return_value=False):
            response = self.client.post(f"{self.url}submit/", {"sql_code": HARDCODED}, format="json")
        self.assertEqual(response.data["grade"]["score"], 0)
        self.assert_no_hidden_leak(response)

    def test_student_cannot_see_hidden_data_staff_can(self):
        self.assertNotIn("hidden_setup_sql", self.client.get(self.url).data)
        listing = self.client.get("/api/labs/").data
        self.assertTrue(all("hidden_setup_sql" not in item for item in listing))
        self.auth_as(self.teacher_a)
        self.assertEqual(self.client.get(self.url).data["hidden_setup_sql"], HIDDEN_SETUP)

    def test_try_mode_uses_only_visible_data(self):
        with patch("labs.checker.run_sql", wraps=run_sql) as runner:
            response = self.run_code("SELECT nomi FROM kitob ORDER BY id", url=f"{self.url}try/")
        self.assertEqual([call.args[1] for call in runner.call_args_list], [self.lab.setup_sql])
        self.assert_no_hidden_leak(response)

    @override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="sinov-kaliti")
    def test_ai_advice_gets_no_hidden_data(self):
        attempt_id = self.run_code(HARDCODED).data["attempt_id"]
        with patch("labs.advice.create_message") as create_message:
            create_message.return_value.content = [type("Block", (), {"type": "text", "text": "savol"})()]
            self.client.post(f"/api/labs/attempts/{attempt_id}/advice/")
        self.assertNotIn("Yashirin", json.dumps(create_message.call_args.kwargs, default=str))

    def test_duplicate_keeps_hidden_data(self):
        self.auth_as(self.teacher_a)
        copy = Lab.objects.get(pk=self.client.post(f"{self.url}duplicate/").data["id"])
        self.assertEqual(copy.hidden_setup_sql, HIDDEN_SETUP)

    def test_validation(self):
        self.auth_as(self.teacher_a)
        cases = {
            # Boshqa jadval
            "CREATE TABLE boshqa (id INT);": "hidden_setup_sql",
            # Ustunlar boshqacha
            "CREATE TABLE kitob (id INT, nomi TEXT);": "hidden_setup_sql",
            # Sintaksis xatosi
            "CREATE TABLE kitob (id INT,;": "hidden_setup_sql",
        }
        for hidden, field in cases.items():
            response = self.client.patch(self.url, {"hidden_setup_sql": hidden}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, hidden)
            self.assertIn(field, response.data, hidden)
        # Yechimsiz laboratoriyada yashirin ma'lumot ma'nosiz
        response = self.client.patch(self.url, {"solution_sql": "", "hidden_setup_sql": HIDDEN_SETUP}, format="json")
        self.assertIn("hidden_setup_sql", response.data)
        response = self.client.patch(self.url, {"hidden_setup_sql": HIDDEN_SETUP}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)


class QueryLabsTests(TestCase):
    """SELECT so'rovlari bo'yicha tayyor laboratoriyalar (query_labs.py)."""

    @staticmethod
    def check(lab_data, code):
        from .checker import check_code

        return check_code(Lab(**lab_data), code)

    def test_solutions_pass_including_hidden_data(self):
        from .query_labs import QUERY_LABS

        for lab_data in QUERY_LABS:
            self.assertTrue(self.check(lab_data, lab_data["solution_sql"])["is_correct"], lab_data["title"])

    def test_hidden_results_differ_from_visible(self):
        from .query_labs import QUERY_LABS

        for lab_data in QUERY_LABS:
            visible = run_sql(lab_data["solution_sql"], lab_data["setup_sql"]).result.rows
            hidden = run_sql(lab_data["solution_sql"], lab_data["hidden_setup_sql"]).result.rows
            self.assertTrue(visible and hidden, lab_data["title"])
            self.assertNotEqual(visible, hidden, lab_data["title"])

    def test_hardcoded_visible_result_fails_every_lab(self):
        from psycopg import sql as psql

        from .query_labs import QUERY_LABS

        for lab_data in QUERY_LABS:
            rows = run_sql(lab_data["solution_sql"], lab_data["setup_sql"]).result.rows
            values = ", ".join(
                "(" + ", ".join(psql.Literal(value).as_string() for value in row) + ")" for row in rows
            )
            columns = ", ".join(f"c{index}" for index in range(len(rows[0])))
            # VALUES qatorlari yozilgan tartibda qaytadi: ko'rinadigan ma'lumotlarda bu to'g'ri natija
            hardcoded = f"SELECT * FROM (VALUES {values}) AS v({columns})"
            result = self.check(lab_data, hardcoded)
            self.assertFalse(result["is_correct"], lab_data["title"])
            self.assertEqual(result["differences"], [HIDDEN_MISMATCH], lab_data["title"])

    def test_alternative_correct_solutions_pass(self):
        from .query_labs import QUERY_LABS

        by_number = {int(lab["title"].split(".")[0].split()[-1]): lab for lab in QUERY_LABS}
        alternatives = {
            1: "SELECT familiya, ism FROM talaba WHERE shahar IN ('Toshkent') ORDER BY 1, 2",
            3: "SELECT ism, familiya FROM talaba WHERE coalesce(shahar, 'Buxoro') IN ('Buxoro', 'Namangan') ORDER BY id",
            4: "SELECT count(ball), avg(ball)::numeric(10,2), max(ball), min(ball) FROM baho",
            5: "SELECT familiya, ism, g.nomi FROM guruh g, talaba t WHERE t.guruh_id = g.id ORDER BY 3, 1",
            6: """SELECT familiya, ism FROM talaba t
                  WHERE NOT EXISTS (SELECT 1 FROM baho b WHERE b.talaba_id = t.id) ORDER BY familiya""",
            7: """SELECT f.nomi, x.soni, x.ortacha FROM fan f JOIN (
                    SELECT fan_id, count(*) AS soni, round(avg(ball), 2) AS ortacha FROM baho GROUP BY fan_id
                  ) x ON x.fan_id = f.id WHERE x.soni >= 3 ORDER BY x.ortacha DESC""",
            8: """WITH o AS (SELECT talaba_id, avg(ball) AS a FROM baho GROUP BY talaba_id)
                  SELECT t.familiya, t.ism, round(o.a, 2) FROM o JOIN talaba t ON t.id = o.talaba_id
                  WHERE o.a > (SELECT avg(ball) FROM baho) ORDER BY o.a DESC""",
            10: """SELECT g.nomi, s.familiya, s.ism, round(s.a, 2) FROM (
                     SELECT DISTINCT ON (t.guruh_id) t.guruh_id, t.familiya, t.ism, avg(b.ball) AS a
                     FROM talaba t JOIN baho b ON b.talaba_id = t.id WHERE t.guruh_id IS NOT NULL
                     GROUP BY t.id ORDER BY t.guruh_id, avg(b.ball) DESC, t.id
                   ) s JOIN guruh g ON g.id = s.guruh_id ORDER BY g.nomi""",
        }
        for number, code in alternatives.items():
            result = self.check(by_number[number], code)
            self.assertTrue(result["is_correct"], (number, result["differences"], result["error"]))

    def test_typical_mistakes_fail(self):
        from .query_labs import QUERY_LABS

        by_number = {int(lab["title"].split(".")[0].split()[-1]): lab for lab in QUERY_LABS}
        mistakes = {
            # NULL ni = bilan solishtirish
            3: "SELECT ism, familiya FROM talaba WHERE shahar = NULL OR shahar IN ('Buxoro', 'Namangan') ORDER BY id",
            # LEFT JOIN o'rniga JOIN: guruhsiz talaba yo'qoladi — bu 5-da to'g'ri, 6-da esa natija bo'sh
            6: "SELECT t.familiya, t.ism FROM talaba t JOIN baho b ON b.talaba_id = t.id WHERE b.ball IS NULL",
            # HAVING o'rniga hamma fanlar
            7: "SELECT f.nomi, count(*), round(avg(b.ball), 2) FROM baho b JOIN fan f ON f.id = b.fan_id GROUP BY f.nomi ORDER BY 3 DESC",
            # RANK o'rniga ROW_NUMBER: teng ballar turli o'rin oladi
            9: """SELECT f.nomi, t.familiya, b.ball, row_number() OVER (PARTITION BY b.fan_id ORDER BY b.ball DESC, t.familiya)
                  FROM baho b JOIN fan f ON f.id = b.fan_id JOIN talaba t ON t.id = b.talaba_id ORDER BY 1, 4, 2""",
        }
        for number, code in mistakes.items():
            self.assertFalse(self.check(by_number[number], code)["is_correct"], number)

    def test_theory_examples_run_and_hide_solutions(self):
        import re

        from .query_labs import EXAMPLE_SETUP_SQL, QUERY_LABS

        for lab_data in QUERY_LABS:
            self.assertNotIn(lab_data["solution_sql"].strip(), lab_data["theory"], lab_data["title"])
            examples = re.findall(r"```sql\n(.*?)```", lab_data["theory"], re.DOTALL)
            self.assertTrue(examples, lab_data["title"])
            for code in examples:
                outcome = run_sql(code, EXAMPLE_SETUP_SQL)
                self.assertIsNone(outcome.error, (lab_data["title"], outcome.error))
                self.assertTrue(outcome.result.rows, lab_data["title"])
                # Namuna universitet jadvallariga emas, do'kon jadvallariga murojaat qiladi
                self.assertIsNone(re.search(r"\b(talaba|baho|guruh|fan)\b", code), lab_data["title"])


class ErSqlLabsTests(BaseTestCase):
    """ER → SQL: berilgan ER-model bo'yicha jadvallar (er_sql_labs.py)."""

    @staticmethod
    def check(lab_data, code):
        from .checker import check_code

        return check_code(Lab(**{k: v for k, v in lab_data.items() if k != "theory"}), code)

    def test_solutions_pass_and_diagrams_are_valid(self):
        from .er import validate_diagram
        from .er_sql_labs import ER_SQL_LABS

        for lab_data in ER_SQL_LABS:
            validate_diagram(lab_data["given_diagram"])
            self.assertTrue(self.check(lab_data, lab_data["solution_sql"])["is_correct"], lab_data["title"])

    def test_diagram_matches_solution_tables(self):
        """Har bir obyekt — jadval, atributlari — ustunlar; M:N uchun oraliq jadval nomlash qoidasi bo'yicha."""
        from .er_sql_labs import ER_SQL_LABS

        for lab_data in ER_SQL_LABS:
            tables = run_sql(lab_data["solution_sql"]).tables
            diagram = lab_data["given_diagram"]
            names = {entity["id"]: entity["name"].lower().replace("'", "") for entity in diagram["entities"]}
            for entity in diagram["entities"]:
                table = names[entity["id"]]
                self.assertIn(table, tables, lab_data["title"])
                for attribute in entity["attributes"]:
                    self.assertIn(attribute["name"], tables[table].columns, (lab_data["title"], table))
            for relationship in diagram["relationships"]:
                if relationship["source_card"] == relationship["target_card"] == "N":
                    junction = f"{names[relationship['source']]}_{names[relationship['target']]}"
                    self.assertIn(junction, tables, lab_data["title"])

    def test_typical_mistakes_fail(self):
        from .er_sql_labs import ER_SQL_LABS

        first, second, third = ER_SQL_LABS
        mistakes = [
            # Tashqi kalit «1» tomonda
            (first, """CREATE TABLE oqituvchi (id SERIAL PRIMARY KEY, ism VARCHAR(100) NOT NULL,
                       telefon VARCHAR(20) NOT NULL UNIQUE, kurs_id INTEGER);
                       CREATE TABLE kurs (id SERIAL PRIMARY KEY, nomi VARCHAR(100) NOT NULL, narx NUMERIC(10,2) NOT NULL);"""),
            # M:N oraliq jadvalsiz: kursga tinglovchi_id qo'shilgan
            (second, second["solution_sql"].split("CREATE TABLE tinglovchi_kurs")[0]),
            # 1:1 uchun UNIQUE unutilgan — bu 1:N bo'lib qoladi
            (third, third["solution_sql"].replace("oqituvchi_id INTEGER UNIQUE REFERENCES", "oqituvchi_id INTEGER REFERENCES")),
        ]
        for lab_data, code in mistakes:
            self.assertFalse(self.check(lab_data, code)["is_correct"], lab_data["title"])

    def test_theory_examples_run_and_hide_solutions(self):
        import re

        from .er_sql_labs import ER_SQL_LABS

        for lab_data in ER_SQL_LABS:
            solution_tables = set(re.findall(r"CREATE TABLE (\w+)", lab_data["solution_sql"]))
            for code in re.findall(r"```sql\n(.*?)```", lab_data["theory"], re.DOTALL):
                self.assertIsNone(run_sql(code).error, lab_data["title"])
                self.assertFalse(solution_tables & set(re.findall(r"CREATE TABLE (\w+)", code)), lab_data["title"])

    def test_student_sees_given_diagram(self):
        from .er_sql_labs import ER_SQL_LABS

        diagram = ER_SQL_LABS[0]["given_diagram"]
        Lab.objects.filter(pk=self.lab.pk).update(given_diagram=diagram)
        self.auth_as(self.student_a1)
        self.assertEqual(self.client.get(self.url).data["given_diagram"]["entities"][0]["name"], "O'qituvchi")

    def test_teacher_saves_validated_diagram(self):
        from .er_sql_labs import ER_SQL_LABS

        self.auth_as(self.teacher_a)
        bad = {"entities": [{"id": "a", "name": "", "x": 0, "y": 0, "attributes": []}], "relationships": []}
        response = self.client.patch(self.url, {"given_diagram": bad}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("given_diagram", response.data)
        diagram = ER_SQL_LABS[1]["given_diagram"]
        response = self.client.patch(self.url, {"given_diagram": diagram}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.lab.refresh_from_db()
        self.assertEqual(len(self.lab.given_diagram["entities"]), 3)
        # Bo'sh diagramma — olib tashlash
        self.client.patch(self.url, {"given_diagram": {"entities": [], "relationships": []}}, format="json")
        self.lab.refresh_from_db()
        self.assertIsNone(self.lab.given_diagram)
        # Nusxalashda o'tadi
        Lab.objects.filter(pk=self.lab.pk).update(given_diagram=diagram)
        copy = Lab.objects.get(pk=self.client.post(f"{self.url}duplicate/").data["id"])
        self.assertEqual(copy.given_diagram, diagram)


class IndexLabsTests(BaseTestCase):
    """Indeks va EXPLAIN: reja talaba sessiyasida tekshiriladi, aldash urinishlari o'tmaydi (index_labs.py)."""

    @staticmethod
    def index_lab(number):
        from .index_labs import INDEX_LABS

        data = dict(INDEX_LABS[number - 1])
        data.pop("theory")
        return Lab(**data)

    def check(self, number, code):
        from .checker import check_code

        return check_code(self.index_lab(number), code)

    def test_solutions_pass(self):
        from .index_labs import INDEX_LABS

        for number, lab_data in enumerate(INDEX_LABS, start=1):
            result = self.check(number, lab_data["solution_sql"])
            self.assertTrue(result["is_correct"], (number, result["differences"]))
            self.assertTrue(any("Index" in line for line in result["plan"]), number)

    def test_wrong_or_missing_indexes_fail(self):
        cases = [
            (1, "SELECT 1", "Seq Scan"),
            (1, "CREATE INDEX ON foydalanuvchi (ism)", "Seq Scan"),
            # Faqat mijoz_id: qidiruv tezlashadi, lekin saralash qoladi
            (2, "CREATE INDEX ON buyurtma (mijoz_id)", "Sort"),
            # Ustunlar tartibi teskari yoki faqat sana: Sort yo'q, lekin reja ancha qimmat
            (2, "CREATE INDEX ON buyurtma (sana, mijoz_id)", "marta yuqori"),
            (2, "CREATE INDEX ON buyurtma (sana)", "marta yuqori"),
            # Oddiy indeks lower(email) ga yordam bermaydi
            (3, "CREATE INDEX ON mijoz (email)", "Seq Scan"),
        ]
        for number, code, node in cases:
            result = self.check(number, code)
            self.assertFalse(result["is_correct"], code)
            self.assertTrue(any(node in item for item in result["differences"]), (code, result["differences"]))

    def test_cheating_attempts_fail(self):
        attempts = [
            "SET enable_seqscan = off",
            "SET enable_seqscan = off; SET enable_sort = off; SET enable_bitmapscan = off",
            # Ma'lumotni o'chirib yuborish yoki jadvalni almashtirish
            "TRUNCATE foydalanuvchi; CREATE INDEX ON foydalanuvchi (email)",
            "DELETE FROM foydalanuvchi WHERE id > 10; CREATE INDEX ON foydalanuvchi (email)",
            "ALTER TABLE foydalanuvchi RENAME TO f2; CREATE VIEW foydalanuvchi AS SELECT * FROM f2",
            "DROP TABLE foydalanuvchi",
        ]
        for code in attempts:
            self.assertFalse(self.check(1, code)["is_correct"], code)

    def test_alternative_correct_indexes_pass(self):
        cases = [
            (1, "ALTER TABLE foydalanuvchi ADD CONSTRAINT email_noyob UNIQUE (email)"),
            (1, "CREATE INDEX ON foydalanuvchi USING hash (email)"),
            (1, "CREATE INDEX ON foydalanuvchi (email, ism)"),
            (2, "CREATE INDEX ON buyurtma (mijoz_id, sana DESC)"),
            (2, "CREATE INDEX ON buyurtma (mijoz_id, sana, summa)"),
            (3, "CREATE INDEX ON mijoz USING hash (lower(email))"),
            (3, "CREATE INDEX ON mijoz ((lower(email)))"),
        ]
        for number, code in cases:
            result = self.check(number, code)
            self.assertTrue(result["is_correct"], (code, result["differences"]))

    def test_try_mode_shows_plan(self):
        from .checker import try_code

        result = try_code(self.index_lab(1), "SELECT 1")
        self.assertTrue(result["plan"][0].startswith("Seq Scan"))
        self.assertNotIn("is_correct", result)

    def test_theory_examples_run(self):
        import re

        from .index_labs import INDEX_LABS

        for lab_data in INDEX_LABS:
            examples = re.findall(r"```sql\n(.*?)```", lab_data["theory"], re.DOTALL)
            self.assertTrue(examples, lab_data["title"])
            for code in examples:
                self.assertIsNone(run_sql(code).error, lab_data["title"])
                self.assertNotIn(lab_data["solution_sql"], code)

    def test_api_visibility_and_validation(self):
        from .index_labs import INDEX_LABS

        lab_data = INDEX_LABS[0]
        self.auth_as(self.teacher_a)
        fields = {"setup_sql": lab_data["setup_sql"], "plan_query": lab_data["plan_query"]}
        # Namunaviy yechim indeks yaratmasa — rad etiladi
        response = self.client.patch(self.url, {**fields, "solution_sql": "SELECT 1"}, format="json")
        self.assertIn("solution_sql", response.data)
        # Indekssiz ham Seq Scan bo'lmasa — laboratoriya hech narsani tekshirmaydi
        response = self.client.patch(
            self.url,
            {**fields, "solution_sql": lab_data["solution_sql"], "plan_query": "SELECT ism FROM foydalanuvchi WHERE id = 5"},
            format="json",
        )
        self.assertIn("plan_query", response.data)
        response = self.client.patch(
            self.url, {**fields, "solution_sql": lab_data["solution_sql"], "plan_forbidden": "Hash Join"}, format="json"
        )
        self.assertIn("plan_forbidden", response.data)
        response = self.client.patch(self.url, {**fields, "solution_sql": lab_data["solution_sql"]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        self.auth_as(self.student_a1)
        data = self.client.get(self.url).data
        self.assertEqual(data["plan_query"], lab_data["plan_query"])
        self.assertNotIn("plan_forbidden", data)
        response = self.run_code("CREATE INDEX ON foydalanuvchi (email)")
        self.assertTrue(response.data["is_correct"], response.data["differences"])
        self.assertTrue(response.data["plan"])
