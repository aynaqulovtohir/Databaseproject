"""ER-diagramma chizish jarayoni: hodisalarni aniqlash, ko'rsatkichlar, API va tadqiqot eksporti."""
import csv
import io
import zipfile
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch
from xml.etree import ElementTree

from django.test import SimpleTestCase, override_settings
from rest_framework import status

from .er import validate_diagram
from .models import ErSnapshot, Lab, LabAttempt
from .process import analyse, diff_events, metrics
from .tests import ER_REFERENCE, BaseTestCase

START = datetime(2026, 10, 1, 9, 0, tzinfo=dt_timezone.utc)


def entity(entity_id, name, *attributes, x=0, y=0):
    return {"id": entity_id, "name": name, "x": x, "y": y,
            "attributes": [{"name": item.lstrip("*"), "key": "pk" if item.startswith("*") else ""} for item in attributes]}


def relationship(relationship_id, source, target, cards=("N", "1"), name=""):
    return {"id": relationship_id, "name": name, "source": source, "target": target,
            "source_card": cards[0], "target_card": cards[1]}


def diagram(entities=(), relationships=()):
    return validate_diagram({"entities": list(entities), "relationships": list(relationships)})


def points(*diagrams, source="edit", minutes=1):
    return [{"at": START + timedelta(minutes=index * minutes), "source": source, "diagram": item}
            for index, item in enumerate(diagrams)]


class DiffTests(SimpleTestCase):
    def activities(self, before, after):
        return [activity for activity, _ in diff_events(before, after)]

    def test_entities_and_attributes(self):
        empty = diagram()
        one = diagram([entity("t", "Talaba", "*id", "ism")])
        self.assertEqual(diff_events(empty, one), [("obyekt_qoshildi", "Talaba")])
        renamed = diagram([entity("t", "Student", "*id", "familiya")])
        self.assertEqual(
            diff_events(one, renamed),
            [("obyekt_nomi_ozgardi", "Talaba → Student"), ("atribut_nomi_ozgardi", "Student: ism → familiya")],
        )
        keyed = diagram([entity("t", "Talaba", "id", "ism", "yosh", "tel")])
        self.assertEqual(
            sorted(self.activities(one, keyed)), ["atribut_qoshildi", "atribut_qoshildi", "kalit_ozgardi"]
        )
        self.assertEqual(self.activities(one, empty), ["obyekt_ochirildi"])

    def test_relationships(self):
        base = [entity("t", "Talaba"), entity("g", "Guruh"), entity("f", "Fan")]
        linked = diagram(base, [relationship("r", "t", "g")])
        self.assertEqual(diff_events(diagram(base), linked), [("boglanish_qoshildi", "Talaba — Guruh")])
        flipped = diagram(base, [relationship("r", "t", "g", ("1", "N"))])
        self.assertEqual(diff_events(linked, flipped), [("kardinallik_ozgardi", "Talaba — Guruh: N:1 → 1:N")])
        moved = diagram(base, [relationship("r", "t", "f", name="o'qiydi")])
        self.assertEqual(self.activities(linked, moved), ["boglanish_qayta_ulandi", "boglanish_nomi_ozgardi"])
        self.assertEqual(self.activities(linked, diagram(base)), ["boglanish_ochirildi"])

    def test_layout_only(self):
        before = diagram([entity("t", "Talaba")])
        after = diagram([entity("t", "Talaba", x=50)])
        self.assertEqual(diff_events(before, after), [("joylashuv_ozgardi", "")])
        self.assertEqual(diff_events(before, before), [])


class MetricsTests(SimpleTestCase):
    reference = validate_diagram(ER_REFERENCE)

    def test_entities_first_and_convergence(self):
        talaba, guruh, fan = entity("t", "Talaba", "*id", "ism"), entity("g", "Guruh", "*id", "nomi"), entity("f", "Fan", "*id", "nomi")
        steps = analyse(
            points(
                diagram([talaba]),
                diagram([talaba, guruh]),
                diagram([talaba, guruh, fan]),
                diagram([talaba, guruh, fan], [relationship("r1", "t", "g")]),
                diagram([talaba, guruh, fan], [relationship("r1", "t", "g"), relationship("r2", "t", "f", ("N", "N"))]),
            ),
            self.reference,
        )
        ratios = [step["ratio"] for step in steps]
        self.assertEqual(ratios, sorted(ratios))
        self.assertEqual(ratios[-1], 1.0)
        result = metrics(steps)
        self.assertEqual(result["strategy"], "avval_obyektlar")
        self.assertEqual(result["entities_first_share"], 1.0)
        self.assertEqual(result["first_relationship_minutes"], 3.0)
        self.assertEqual(result["churn"], 0.0)

    def test_trial_and_error_and_sessions(self):
        a, b = entity("t", "Talaba"), entity("g", "Guruh")
        sequence = [diagram([a]), diagram([a, b]), diagram([a]), diagram([a, b]), diagram([b]), diagram([a, b])]
        result_points = points(*sequence)
        result_points[-1]["at"] += timedelta(hours=2)
        steps = analyse(result_points, self.reference)
        self.assertEqual(steps[-1]["session"], 2)
        result = metrics(steps)
        self.assertEqual(result["strategy"], "sinab_korish")
        self.assertEqual(result["sessions"], 2)
        # 2 soatlik tanaffus faol vaqtga 5 daqiqa bo'lib kiradi
        self.assertEqual(result["active_minutes"], 4 + 5)

    def test_few_events(self):
        self.assertEqual(metrics(analyse(points(diagram([entity("t", "Talaba")])), self.reference))["strategy"], "aniqlanmadi")
        self.assertIsNone(metrics([]))


class ProcessBase(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.er_lab = Lab.objects.create(
            kind=Lab.Kind.ER, title="Universitet ER", description="d", reference_diagram=ER_REFERENCE, author=cls.teacher_a
        )
        cls.er_lab.groups.add(cls.group_a)
        cls.snapshot_url = f"/api/labs/{cls.er_lab.pk}/er-snapshot/"
        cls.process_url = f"/api/labs/{cls.er_lab.pk}/process/"

    def send(self, value, url=None):
        return self.client.post(url or self.snapshot_url, {"diagram": value}, format="json")


class ProcessApiTests(ProcessBase):

    def test_student_snapshots_are_saved_once_per_change(self):
        self.auth_as(self.student_a1)
        one = {"entities": [entity("t", "Talaba")], "relationships": []}
        self.assertEqual(self.send(one).status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.send(one).status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(ErSnapshot.objects.count(), 1)
        one["entities"].append(entity("g", "Guruh"))
        self.send(one)
        self.assertEqual(ErSnapshot.objects.count(), 2)
        # Saqlanadigan diagramma tozalangan: noma'lum maydonlar tashlanadi
        one["entities"][0]["extra"] = "<script>"
        one["entities"][0]["x"] = 5
        self.send(one)
        self.assertNotIn("extra", ErSnapshot.objects.last().diagram["entities"][0])

    def test_snapshot_validation_and_access(self):
        self.auth_as(self.student_a1)
        bad = {"entities": [entity("a", "X"), entity("b", "x")], "relationships": []}
        self.assertEqual(self.send(bad).status_code, status.HTTP_400_BAD_REQUEST)
        sql_lab_url = f"/api/labs/{self.lab.pk}/er-snapshot/"
        self.assertEqual(self.send(diagram(), sql_lab_url).status_code, status.HTTP_400_BAD_REQUEST)
        self.auth_as(self.student_b)  # laboratoriya uning guruhiga berilmagan
        self.assertEqual(self.send(diagram()).status_code, status.HTTP_404_NOT_FOUND)
        self.auth_as(self.teacher_a)
        self.assertEqual(self.send(diagram()).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ErSnapshot.objects.count(), 0)

    def test_snapshot_limit(self):
        self.auth_as(self.student_a1)
        with patch("labs.process.MAX_SNAPSHOTS", 2):
            for name in ("A", "B", "C"):
                self.assertEqual(self.send(diagram([entity("t", name)])).status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(ErSnapshot.objects.count(), 2)

    def test_teacher_replay(self):
        self.auth_as(self.student_a1)
        self.send(diagram([entity("t", "Talaba", "*id", "ism")]))
        self.client.post(f"/api/labs/{self.er_lab.pk}/run/", {"diagram": ER_REFERENCE}, format="json")

        self.auth_as(self.teacher_a)
        response = self.client.get(self.process_url, {"student": self.student_a1.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        steps = response.data["steps"]
        self.assertEqual([step["source"] for step in steps], ["edit", "run"])
        self.assertEqual(steps[0]["events"][0]["activity"], "obyekt_qoshildi")
        self.assertEqual(steps[-1]["events"][-1]["activity"], "tekshirish")
        self.assertEqual(steps[-1]["ratio"], 1.0)
        self.assertEqual(steps[-1]["diagram"]["entities"][0]["name"], "Talaba")
        self.assertEqual(response.data["metrics"]["checks"], 1)

        self.assertEqual(self.client.get(self.process_url, {"student": "x"}).status_code, status.HTTP_400_BAD_REQUEST)
        # Laboratoriya berilmagan guruh talabasi
        response = self.client.get(self.process_url, {"student": self.student_b.pk})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.auth_as(self.teacher_b)
        response = self.client.get(self.process_url, {"student": self.student_a1.pk})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.auth_as(self.student_a1)
        response = self.client.get(self.process_url, {"student": self.student_a1.pk})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ProcessExportTests(ProcessBase):
    def setUp(self):
        super().setUp()
        self.auth_as(self.student_a1)
        self.send(diagram([entity("t", "Maxfiy-nom", "*id")]))
        self.send(diagram([entity("t", "Maxfiy-nom", "*id"), entity("g", "Guruh")]))
        self.client.post(f"/api/labs/{self.er_lab.pk}/submit/", {"diagram": ER_REFERENCE}, format="json")
        self.auth_as(self.student_a2)
        self.send(diagram([entity("t", "Talaba")]))

    def export(self):
        self.auth_as(self.teacher_a)
        response = self.client.get("/api/labs/research-export/")
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        files = {name: archive.read(name).decode("utf-8-sig") for name in archive.namelist()}
        tables = {name: list(csv.DictReader(io.StringIO(files[name]), delimiter=";"))
                  for name in ("er_jarayon.csv", "er_jarayon_hodisalari.csv")}
        return files, tables

    @override_settings(RESEARCH_CONSENT_REQUIRED=False)
    def test_event_log_and_metrics(self):
        from .research import pseudonym

        files, tables = self.export()
        events = [row for row in tables["er_jarayon_hodisalari.csv"] if row["talaba"] == pseudonym(self.student_a1.pk)]
        self.assertEqual(
            [row["hodisa"] for row in events],
            ["obyekt_qoshildi", "obyekt_qoshildi", "obyekt_nomi_ozgardi", "atribut_qoshildi", "atribut_qoshildi",
             "atribut_qoshildi", "obyekt_qoshildi", "boglanish_qoshildi", "boglanish_qoshildi", "topshirish"],
        )
        self.assertEqual(events[0]["case_id"], f"{pseudonym(self.student_a1.pk)}-L{self.er_lab.pk}-S1")
        self.assertEqual(events[-1]["moslik"], "1.0")
        self.assertEqual(len(tables["er_jarayon.csv"]), 2)
        row = next(row for row in tables["er_jarayon.csv"] if row["talaba"] == pseudonym(self.student_a1.pk))
        self.assertEqual(row["tekshiruvlar"], "1")
        self.assertEqual(row["eng_yuqori_baho"], "100")
        # Ism va obyekt nomlari eksportga kirmaydi
        for content in files.values():
            self.assertNotIn("Maxfiy-nom", content)
            self.assertNotIn("student_a1", content)
        # XES to'g'ri XML: har bir talaba-sessiya uchun bitta iz
        log = ElementTree.fromstring(files["er_jarayon.xes"].encode())
        traces = log.findall("{http://www.xes-standard.org/}trace")
        self.assertEqual(len(traces), 2)
        self.assertEqual(len(traces[0].findall("{http://www.xes-standard.org/}event")) + len(
            traces[1].findall("{http://www.xes-standard.org/}event")), len(tables["er_jarayon_hodisalari.csv"]))

    def test_only_consenting_students(self):
        from .research import pseudonym

        self.student_a2.research_consent = True
        self.student_a2.save(update_fields=["research_consent"])
        _, tables = self.export()
        students = {row["talaba"] for row in tables["er_jarayon_hodisalari.csv"]}
        self.assertEqual(students, {pseudonym(self.student_a2.pk)})
        self.assertEqual([row["talaba"] for row in tables["er_jarayon.csv"]], [pseudonym(self.student_a2.pk)])
