"""View, funksiya va trigger laboratoriyalari: tayyor laboratoriyalar va tipik xatolar ushlanishi (qum quti bilan)."""
from .checker import check_code
from .evolution import validate_lab_queries, validate_queries
from .models import Lab
from .programmability_labs import PROGRAMMABILITY_LABS
from .tests import BaseTestCase


def lab_from(data):
    return Lab(
        setup_sql=data["setup_sql"], solution_sql=data["solution_sql"], hidden_setup_sql=data["hidden_setup_sql"],
        check_queries=validate_queries(data["check_queries"]), topic=data["topic"],
    )


class ProgrammabilityLabsTests(BaseTestCase):
    def test_ready_labs_are_valid_and_solutions_pass(self):
        for data in PROGRAMMABILITY_LABS:
            with self.subTest(lab=data["title"]):
                lab = lab_from(data)
                validate_lab_queries(data["setup_sql"], data["solution_sql"], data["hidden_setup_sql"], lab.check_queries)
                result = check_code(lab, data["solution_sql"])
                self.assertTrue(result["is_correct"], result)
                self.assertEqual(lab.effective_topic, Lab.Topic.PROGRAMMABILITY)

    def assert_fails(self, data, code, query_id=None):
        result = check_code(lab_from(data), code)
        self.assertFalse(result["is_correct"], result)
        if query_id:
            failed = [item["id"] for item in result["queries"] if not item["passed"]]
            self.assertIn(query_id, failed, result)
        return result

    def test_table_instead_of_view(self):
        data = PROGRAMMABILITY_LABS[0]
        result = self.assert_fails(data, data["solution_sql"].replace("CREATE VIEW reyting AS", "CREATE TABLE reyting AS"), "yangilanish")
        self.assertIn("Ortiqcha jadval: «reyting»", " ".join(result["differences"]))

    def test_inner_join_hides_students_without_grades(self):
        data = PROGRAMMABILITY_LABS[0]
        self.assert_fails(data, data["solution_sql"].replace("LEFT JOIN", "JOIN"), "reyting")

    def test_function_without_coalesce(self):
        data = PROGRAMMABILITY_LABS[1]
        self.assert_fails(data, data["solution_sql"].replace("COALESCE(SUM(q.narx * q.miqdor), 0)", "SUM(q.narx * q.miqdor)"), "yoq")

    def test_trigger_that_logs_every_update(self):
        data = PROGRAMMABILITY_LABS[2]
        always = data["solution_sql"].replace("IF NEW.narx IS DISTINCT FROM OLD.narx THEN", "IF TRUE THEN")
        result = self.assert_fails(data, always)
        failed = {item["id"] for item in result["queries"] if not item["passed"]}
        self.assertEqual(failed, {"nom", "teng"})

    def test_trigger_on_insert_only_never_logs(self):
        data = PROGRAMMABILITY_LABS[2]
        self.assert_fails(data, data["solution_sql"].replace("AFTER UPDATE ON mahsulot", "AFTER INSERT ON mahsulot"), "ikki-marta")
