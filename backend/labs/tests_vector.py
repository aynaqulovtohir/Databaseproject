"""Vektorli qidiruv (pgvector) laboratoriyalari va kengaytma sxemasining himoyasi."""
from django.test import SimpleTestCase

from .checker import check_code
from .models import Lab
from .sandbox import available_extensions, run_sql
from .vector_labs import VECTOR_LABS


def lab(number):
    data = dict(VECTOR_LABS[number])
    data.pop("theory")
    return Lab(**data)


class VectorLabsTests(SimpleTestCase):
    def test_extension_is_installed(self):
        self.assertIn("vector", available_extensions())

    def test_solutions_pass_and_shortcuts_fail(self):
        for number, data in enumerate(VECTOR_LABS):
            self.assertTrue(check_code(lab(number), data["solution_sql"])["is_correct"], data["title"])
        wrong = [
            # Masofa o'rniga id bo'yicha
            (0, "SELECT sarlavha FROM maqola ORDER BY id LIMIT 3"),
            # L2 o'rniga kosinus — boshqa tartib
            (0, "SELECT sarlavha FROM maqola ORDER BY embedding <=> '[0.9, 0.2, 0.0]' LIMIT 3"),
            # Natijani qo'lda yozish yashirin ma'lumotlarda o'tmaydi
            (0, "SELECT 'Tranzaksiyalar' UNION ALL SELECT 'SQL JOIN turlari' UNION ALL SELECT 'Indekslar qanday ishlaydi'"),
            # Filtrsiz
            (1, "SELECT sarlavha, round((embedding <=> '[0.5, 0.0, 0.5]')::numeric, 3) AS masofa FROM maqola "
                "ORDER BY embedding <=> '[0.5, 0.0, 0.5]' LIMIT 2"),
        ]
        for number, code in wrong:
            self.assertFalse(check_code(lab(number), code)["is_correct"], code)

    def test_student_cannot_change_extension_schema(self):
        for code in (
            "CREATE TABLE ext.x (id INT)",
            "DROP EXTENSION vector",
            "CREATE FUNCTION ext.f() RETURNS INT AS 'SELECT 1' LANGUAGE sql",
            "ALTER EXTENSION vector UPDATE",
        ):
            self.assertIsNotNone(run_sql(code).error, code)
        # Indeks yaratish (o'z jadvalida) ruxsat etilgan
        setup = "CREATE TABLE t (e vector(3)); INSERT INTO t VALUES ('[1,2,3]')"
        self.assertIsNone(run_sql("CREATE INDEX ON t USING hnsw (e vector_l2_ops)", setup).error)
