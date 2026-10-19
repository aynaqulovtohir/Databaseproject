"""Qatorlar darajasida himoya (RLS) laboratoriyalari: tayyor laboratoriyalar va tipik xatolar (qum quti bilan)."""
from .checker import check_code
from .evolution import validate_lab_queries, validate_queries
from .models import Lab
from .security_labs import SECURITY_LABS
from .tests import BaseTestCase


def lab_from(data):
    return Lab(
        setup_sql=data["setup_sql"], solution_sql=data["solution_sql"], hidden_setup_sql=data["hidden_setup_sql"],
        check_queries=validate_queries(data["check_queries"]), topic=data["topic"],
    )


class SecurityLabsTests(BaseTestCase):
    def failed(self, data, code):
        result = check_code(lab_from(data), code)
        self.assertFalse(result["is_correct"], result)
        return {item["id"] for item in result["queries"] if not item["passed"]}

    def test_ready_labs_are_valid_and_solutions_pass(self):
        for data in SECURITY_LABS:
            with self.subTest(lab=data["title"]):
                lab = lab_from(data)
                validate_lab_queries(data["setup_sql"], data["solution_sql"], data["hidden_setup_sql"], lab.check_queries)
                result = check_code(lab, data["solution_sql"])
                self.assertTrue(result["is_correct"], result)
                self.assertEqual(lab.effective_topic, Lab.Topic.SECURITY)

    def test_without_force_owner_sees_everything(self):
        data = SECURITY_LABS[0]
        failed = self.failed(data, data["solution_sql"].replace("ALTER TABLE baho FORCE ROW LEVEL SECURITY;", ""))
        self.assertIn("birinchi", failed)

    def test_empty_setting_without_nullif_errors(self):
        data = SECURITY_LABS[0]
        code = data["solution_sql"].replace("NULLIF(current_setting('app.talaba_id', true), '')::int",
                                            "current_setting('app.talaba_id', true)::int")
        self.assertIn("bosh", self.failed(data, code))

    def test_enabled_without_policy_hides_everything(self):
        data = SECURITY_LABS[0]
        code = "ALTER TABLE baho ENABLE ROW LEVEL SECURITY; ALTER TABLE baho FORCE ROW LEVEL SECURITY;"
        self.assertIn("birinchi", self.failed(data, code))

    def test_clinic_doctor_only_policy_hides_patients_and_chief(self):
        data = SECURITY_LABS[1]
        code = """
        ALTER TABLE qabul ENABLE ROW LEVEL SECURITY;
        ALTER TABLE qabul FORCE ROW LEVEL SECURITY;
        CREATE POLICY shifokor ON qabul USING (shifokor_id = NULLIF(current_setting('app.user_id', true), '')::int);
        """
        failed = self.failed(data, code)
        self.assertTrue({"bemor", "bosh", "nomalum"} <= failed, failed)
