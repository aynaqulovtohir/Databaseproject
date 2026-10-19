"""Ma'lumotlar ombori va JSONB laboratoriyalari: tayyor laboratoriyalar va tipik xatolar (qum quti bilan)."""
from .checker import check_code, validate_lab_sql
from .evolution import validate_lab_queries, validate_queries
from .models import Lab
from .tests import BaseTestCase
from .warehouse_labs import WAREHOUSE_LABS


def lab_from(data):
    return Lab(
        setup_sql=data["setup_sql"], solution_sql=data["solution_sql"], hidden_setup_sql=data["hidden_setup_sql"],
        check_queries=validate_queries(data.get("check_queries", [])), topic=data["topic"],
    )


class WarehouseLabsTests(BaseTestCase):
    def test_ready_labs_are_valid_and_solutions_pass(self):
        for data in WAREHOUSE_LABS:
            with self.subTest(lab=data["title"]):
                lab = lab_from(data)
                validate_lab_sql(data["setup_sql"], data["solution_sql"], data["hidden_setup_sql"])
                if lab.check_queries:
                    validate_lab_queries(data["setup_sql"], data["solution_sql"], data["hidden_setup_sql"], lab.check_queries)
                result = check_code(lab, data["solution_sql"])
                self.assertTrue(result["is_correct"], result)

    def assert_wrong(self, index, code):
        result = check_code(lab_from(WAREHOUSE_LABS[index]), code)
        self.assertFalse(result["is_correct"], result)
        return result

    def test_star_schema_summa_without_quantity(self):
        data = WAREHOUSE_LABS[0]
        self.assert_wrong(0, data["solution_sql"].replace("miqdor * narx FROM savdo", "narx FROM savdo"))

    def test_rollup_without_subtotals(self):
        data = WAREHOUSE_LABS[1]
        self.assert_wrong(1, data["solution_sql"].replace("GROUP BY ROLLUP (d.shahar, d.nomi)", "GROUP BY d.shahar, d.nomi"))

    def test_jsonb_text_comparison_of_numbers(self):
        # "1024" < "128" matn sifatida: son turiga keltirilmasa yashirin ma'lumotda xato chiqadi
        data = WAREHOUSE_LABS[2]
        code = data["solution_sql"].replace("(xususiyat ->> 'xotira')::int >= 128", "xususiyat ->> 'xotira' >= '128'")
        result = self.assert_wrong(2, code)
        self.assertIn("yashirin", " ".join(result["differences"]))

    def test_jsonb_only_first_array_element(self):
        data = WAREHOUSE_LABS[3]
        code = data["solution_sql"].replace(
            "SELECT b.id, e ->> 'nomi', (e ->> 'soni')::int\nFROM buyurtma b, jsonb_array_elements(b.malumot -> 'mahsulotlar') AS e;",
            "SELECT id, malumot -> 'mahsulotlar' -> 0 ->> 'nomi', (malumot -> 'mahsulotlar' -> 0 ->> 'soni')::int\n"
            "FROM buyurtma WHERE jsonb_array_length(malumot -> 'mahsulotlar') > 0;",
        )
        self.assertNotEqual(code, data["solution_sql"])
        self.assert_wrong(3, code)
