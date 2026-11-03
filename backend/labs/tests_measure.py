"""Pilot o'lchov topshiriqlari (measure_labs.py) va topshirishdagi yozma asoslash."""
from collections import Counter
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import StudentGroup, User

from .blind_review import item_payload
from .design_labs import ALL_LABS
from .er import validate_diagram
from .measure_labs import MEASURE_LABS
from .models import Lab, LabAttempt, LabGrade, LabModule


def shape(diagram):
    """Diagramma tuzilishi: obyektlar, atributlar soni va bog'lanish turlari (nomlarga bog'liq emas)."""
    rels = diagram["relationships"]
    cards = Counter(tuple(sorted((r["source_card"], r["target_card"]))) for r in rels)
    events = Counter(r["target"] for r in rels if (r["source_card"], r["target_card"]) == ("1", "N"))
    return (
        len(diagram["entities"]),
        sum(len(e["attributes"]) for e in diagram["entities"]),
        tuple(sorted(cards.items())),
        tuple(sorted(events.values())),
    )


class MeasureLabsShapeTests(SimpleTestCase):
    def test_three_isomorphic_tasks(self):
        self.assertEqual(len(MEASURE_LABS), 3)
        shapes = {shape(lab["reference_diagram"]) for lab in MEASURE_LABS}
        # 4 obyekt, 11 atribut, bitta M:N va ikkita 1:N — ikkalasi ham bitta hodisa obyektiga
        self.assertEqual(shapes, {(4, 11, ((("1", "N"), 2), (("N", "N"), 1)), (2,))})

    def test_same_shape_as_practice_template_but_not_in_practice_list(self):
        template = next(lab for lab in ALL_LABS if lab["title"] == "ER-model 2. Kutubxona")
        self.assertEqual(shape(template["reference_diagram"]), shape(MEASURE_LABS[0]["reference_diagram"]))
        practice = {lab["title"] for lab in ALL_LABS}
        self.assertFalse(practice & {lab["title"] for lab in MEASURE_LABS})

    def test_diagrams_valid_and_description_lists_every_attribute(self):
        for lab in MEASURE_LABS:
            validate_diagram(lab["reference_diagram"])
            self.assertTrue(lab["ask_justification"])
            for entity in lab["reference_diagram"]["entities"]:
                line = f"- {entity['name']}: " + ", ".join(a["name"] for a in entity["attributes"])
                self.assertIn(line, lab["description"])


class SeedMeasureLabsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user("m_teacher", role=User.Role.TEACHER)
        cls.group = StudentGroup.objects.create(name="P-1")
        cls.other = StudentGroup.objects.create(name="P-2")
        now = timezone.now()
        cls.exam = LabModule.objects.create(title="O'lchov", author=cls.teacher, sequential=False,
                                            exam_starts_at=now, exam_ends_at=now + timedelta(hours=1))
        cls.plain = LabModule.objects.create(title="Oddiy", author=cls.teacher)

    def seed(self, *args):
        call_command("seed_measure_labs", "--author", "m_teacher", *args, stdout=StringIO())

    def test_creates_labs_once_and_adds_groups(self):
        self.seed("--group", "P-1", "--module", str(self.exam.pk))
        labs = Lab.objects.filter(title__startswith="O'lchov ER-")
        self.assertEqual(labs.count(), 3)
        self.assertTrue(all(lab.ask_justification and lab.module_id == self.exam.pk for lab in labs))
        self.seed("--group", "P-2")
        self.assertEqual(Lab.objects.filter(title__startswith="O'lchov ER-").count(), 3)
        self.assertEqual(set(labs.first().groups.values_list("name", flat=True)), {"P-1", "P-2"})

    def test_module_must_be_exam(self):
        with self.assertRaisesMessage(CommandError, "imtihon vaqti"):
            self.seed("--group", "P-1", "--module", str(self.plain.pk))
        with self.assertRaises(CommandError):
            self.seed("--group", "yoq")


class JustificationSubmitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user("j_teacher", role=User.Role.TEACHER)
        cls.group = StudentGroup.objects.create(name="J-1", ai_enabled=False)
        cls.student = User.objects.create_user("j_student", role=User.Role.STUDENT, group=cls.group)
        data = MEASURE_LABS[0]
        cls.asked = Lab.objects.create(author=cls.teacher, **data)
        cls.plain = Lab.objects.create(author=cls.teacher, kind=Lab.Kind.ER, title="Oddiy ER", description="d",
                                       reference_diagram=data["reference_diagram"])
        for lab in (cls.asked, cls.plain):
            lab.groups.add(cls.group)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.student)

    def submit(self, lab, **extra):
        return self.client.post(f"/api/labs/{lab.pk}/submit/", {"diagram": lab.reference_diagram, **extra}, format="json")

    def test_student_sees_flag(self):
        self.assertTrue(self.client.get(f"/api/labs/{self.asked.pk}/").data["ask_justification"])
        self.assertFalse(self.client.get(f"/api/labs/{self.plain.pk}/").data["ask_justification"])

    def test_justification_saved_and_shown_to_blind_reviewer(self):
        text = "  Bron alohida obyekt: uning sanalari bor va u xona hamda mehmonga bog'lanadi.  "
        self.assertEqual(self.submit(self.asked, justification=text).status_code, 200)
        attempt = LabAttempt.objects.get(lab=self.asked, is_submission=True)
        self.assertEqual(attempt.justification, text.strip())
        grade = LabGrade.objects.get(lab=self.asked, student=self.student)
        self.assertEqual(item_payload(grade)["justification"], text.strip())

    def test_ignored_when_not_asked_and_optional_when_asked(self):
        self.assertEqual(self.submit(self.plain, justification="kerak emas").status_code, 200)
        self.assertEqual(LabAttempt.objects.get(lab=self.plain, is_submission=True).justification, "")
        self.assertEqual(self.submit(self.asked).status_code, 200)
        self.assertEqual(LabAttempt.objects.get(lab=self.asked, is_submission=True).justification, "")

    def test_rejects_too_long_or_non_text(self):
        self.assertEqual(self.submit(self.asked, justification="x" * 2001).status_code, 400)
        self.assertEqual(self.submit(self.asked, justification=["ro'yxat"]).status_code, 400)
        self.assertFalse(LabAttempt.objects.filter(lab=self.asked, is_submission=True).exists())
