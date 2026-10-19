"""Teskari loyihalash: bazadan namunaviy ER-diagramma hosil qilish va laboratoriya API'si (qum quti bilan)."""
from django.test import override_settings
from rest_framework import status

from .er import compare, normalize
from .models import Lab
from .reverse import ReverseError, diagram_from_sql, schema_to_diagram
from .tests import BaseTestCase

SCHEMA = """
CREATE TABLE guruh (id INT PRIMARY KEY, nomi TEXT NOT NULL);
CREATE TABLE talaba (id INT PRIMARY KEY, ism TEXT, guruh_id INT REFERENCES guruh (id));
CREATE TABLE pasport (id INT PRIMARY KEY, raqam TEXT, talaba_id INT UNIQUE REFERENCES talaba (id));
CREATE TABLE fan (id INT PRIMARY KEY, nomi TEXT);
CREATE TABLE talaba_fan (talaba_id INT REFERENCES talaba (id), fan_id INT REFERENCES fan (id), PRIMARY KEY (talaba_id, fan_id));
CREATE TABLE baholash (id INT PRIMARY KEY, talaba_id INT REFERENCES talaba (id), fan_id INT REFERENCES fan (id), baho INT);
CREATE TABLE xodim (id INT PRIMARY KEY, ism TEXT, rahbar_id INT REFERENCES xodim (id));
"""


def relations(diagram):
    """{(manba, nishon): (kardinallik, nom)} — obyekt nomlari bilan."""
    names = {entity["id"]: entity["name"] for entity in diagram["entities"]}
    return {
        (names[item["source"]], names[item["target"]]): (f"{item['source_card']}:{item['target_card']}", item["name"])
        for item in diagram["relationships"]
    }


class SchemaToDiagramTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.diagram = diagram_from_sql(SCHEMA)

    def test_entities_and_keys(self):
        entities = {entity["name"]: entity for entity in self.diagram["entities"]}
        # Faqat kalitlardan iborat oraliq jadval obyekt emas — M:N bog'lanish
        self.assertEqual(set(entities), {"guruh", "talaba", "pasport", "fan", "baholash", "xodim"})
        keys = {item["name"]: item["key"] for item in entities["talaba"]["attributes"]}
        self.assertEqual(keys, {"id": "pk", "ism": "", "guruh_id": "fk"})

    def test_relationships(self):
        self.assertEqual(
            relations(self.diagram),
            {
                ("talaba", "guruh"): ("N:1", ""),
                ("pasport", "talaba"): ("1:1", ""),
                ("talaba", "fan"): ("N:N", "talaba_fan"),
                ("baholash", "talaba"): ("N:1", ""),
                ("baholash", "fan"): ("N:1", ""),
                ("xodim", "xodim"): ("N:1", ""),
            },
        )

    def test_student_equivalent_diagram_is_correct(self):
        self.assertEqual(compare(self.diagram, self.diagram)["differences"], [])
        # Talaba nomlarni bosh harf bilan yozgan, FK atributlarni chizmagan, o'z-o'ziga bog'lanishni teskari chizgan
        student = {
            "entities": [
                {**entity, "name": entity["name"].title(),
                 "attributes": [item for item in entity["attributes"] if item["key"] != "fk"]}
                for entity in self.diagram["entities"]
            ],
            "relationships": [
                {**item, "source_card": item["target_card"], "target_card": item["source_card"]}
                if item["source"] == item["target"] else item
                for item in self.diagram["relationships"]
            ],
        }
        self.assertEqual(compare(student, self.diagram)["differences"], [])

    def test_errors(self):
        with self.assertRaises(ReverseError):
            schema_to_diagram({})
        self.assertEqual(normalize("Talaba_Fan"), "talaba_fan")


@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="")
class ReverseLabApiTests(BaseTestCase):
    def create(self, **data):
        self.auth_as(self.teacher_a)
        body = {"kind": "er", "title": "Teskari", "description": "d", "setup_sql": SCHEMA, "groups": [self.group_a.pk], **data}
        return self.client.post("/api/labs/", body, format="json")

    def test_teacher_saves_sql_and_reference_is_derived(self):
        response = self.create()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(len(response.data["reference_diagram"]["entities"]), 6)
        self.assertEqual(response.data["setup_sql"], SCHEMA)
        lab = Lab.objects.get(pk=response.data["id"])

        self.auth_as(self.student_a1)
        data = self.client.get(f"/api/labs/{lab.pk}/").data
        self.assertEqual(data["setup_sql"], SCHEMA)
        self.assertNotIn("reference_diagram", data)
        result = self.client.post(f"/api/labs/{lab.pk}/run/", {"diagram": lab.reference_diagram}, format="json").data
        self.assertTrue(result["is_correct"], result)

        # SQL o'zgarsa namuna qayta hosil qilinadi
        self.auth_as(self.teacher_a)
        response = self.client.patch(f"/api/labs/{lab.pk}/", {"setup_sql": "CREATE TABLE kitob (id INT PRIMARY KEY);"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual([item["name"] for item in response.data["reference_diagram"]["entities"]], ["kitob"])

    def test_invalid_input(self):
        response = self.create(setup_sql="CREATE TABLE (")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("setup_sql", response.data)
        response = self.create(setup_sql="SELECT 1;")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("jadval", str(response.data["setup_sql"]))
        requirement = [{"id": "R1", "text": "Talaba bor", "kind": "entity"}]
        response = self.create(requirements=requirement)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_regular_er_lab_still_needs_reference(self):
        response = self.create(setup_sql="")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reference_diagram", response.data)


class ReadyReverseLabsTests(BaseTestCase):
    def test_ready_labs_produce_expected_models(self):
        from .reverse_labs import REVERSE_LABS

        expected = [
            ({"kafedra", "oqituvchi", "fan"}, {("oqituvchi", "kafedra"): ("N:1", ""), ("fan", "oqituvchi"): ("N:1", "")}),
            (
                {"shifokor", "mutaxassislik", "bemor", "tibbiy_karta", "qabul"},
                {
                    ("shifokor", "mutaxassislik"): ("N:N", "shifokor_mutaxassislik"),
                    ("tibbiy_karta", "bemor"): ("1:1", ""),
                    ("qabul", "shifokor"): ("N:1", ""),
                    ("qabul", "bemor"): ("N:1", ""),
                },
            ),
            (
                {"bolim", "xodim", "loyiha"},
                {
                    ("xodim", "bolim"): ("N:1", ""),
                    ("xodim", "xodim"): ("N:1", ""),
                    ("bolim", "xodim"): ("1:1", ""),
                    ("xodim", "loyiha"): ("N:N", "xodim_loyiha"),
                },
            ),
        ]
        for data, (entities, links) in zip(REVERSE_LABS, expected):
            with self.subTest(lab=data["title"]):
                diagram = diagram_from_sql(data["setup_sql"])
                self.assertEqual({entity["name"] for entity in diagram["entities"]}, entities)
                self.assertEqual(relations(diagram), links)
                self.assertTrue(data["theory"].strip())
                # Nazariyadagi misol laboratoriya jadvallarini oshkor qilmaydi
                for name in entities:
                    self.assertNotIn(f"CREATE TABLE {name} ", data["theory"])

    def test_two_relationships_between_same_pair_are_both_checked(self):
        from .reverse_labs import REVERSE_LABS

        reference = diagram_from_sql(REVERSE_LABS[2]["setup_sql"])
        # Talaba "boshqaradi" (1:1) bog'lanishini chizmagan
        ids = {entity["id"] for entity in reference["entities"] if entity["name"] in ("bolim", "xodim")}
        names = {entity["id"]: entity["name"] for entity in reference["entities"]}
        student = {
            **reference,
            "relationships": [
                item for item in reference["relationships"]
                if not (names[item["source"]] == "bolim" and names[item["target"]] == "xodim")
            ],
        }
        self.assertTrue(ids)
        differences = compare(student, reference)["differences"]
        self.assertEqual(len(differences), 1)
        self.assertIn("bog'lanish yetishmaydi", differences[0])
