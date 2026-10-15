"""Virtual laboratoriya: ruxsatlar, kodni tekshirish va maslahat testlari.

Bu testlar haqiqiy "qum quti" bazasida (LAB_SANDBOX_DB) SQL bajaradi.
"""
from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from ai.client import AITransientError
from users.models import StudentGroup, User

from .models import Lab, LabAttempt, LabGrade
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
        self.assertEqual(self.client.post(self.advice_url).data, {"advice": "FROM so'zini tekshiring."})
        self.assertEqual(self.client.post(self.advice_url).data, {"advice": "FROM so'zini tekshiring."})
        generate.assert_called_once()

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

    @override_settings(LAB_AI_DAILY_LIMIT=1)
    @patch("labs.views.generate_advice", return_value="Maslahat")
    def test_daily_limit(self, generate):
        self.assertEqual(self.client.post(self.advice_url).status_code, status.HTTP_200_OK)
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
        # Ro'yxatda 1-laboratoriya birinchi turadi
        self.assertTrue(labs.order_by("-created_at", "-id").first().title.startswith("Loyihalash 1."))

        with self.assertRaises(CommandError):
            call_command("seed_design_labs", author="student_a1", stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command("seed_design_labs", author="teacher_a", group=["Yo'q-guruh"], stdout=StringIO())
