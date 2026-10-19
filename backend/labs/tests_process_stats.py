"""ER-diagramma chizish jarayoni statistikasi: egri chiziq, strategiyalar, AI va nazorat guruhlari, o'tishlar."""
from datetime import timedelta

from django.test import SimpleTestCase, override_settings
from rest_framework import status

from users.models import User

from .models import ErSnapshot, Lab, LabAttempt, LabGrade
from .process_stats import curve
from .tests import ER_REFERENCE, PASSWORD, BaseTestCase
from .tests_process import START, diagram, entity, relationship

URL = "/api/statistics/er-process/"

TALABA = entity("t", "Talaba", "*id", "ism")
GURUH = entity("g", "Guruh", "*id", "nomi")
FAN = entity("f", "Fan", "*id", "nomi")
FULL = diagram([TALABA, GURUH, FAN], [relationship("r1", "t", "g"), relationship("r2", "t", "f", ("N", "N"))])

# Avval obyektlar, keyin bog'lanishlar
ENTITIES_FIRST = [
    diagram([TALABA]),
    diagram([TALABA, GURUH]),
    diagram([TALABA, GURUH, FAN]),
    diagram([TALABA, GURUH, FAN], [relationship("r1", "t", "g")]),
    FULL,
]
# Ko'p o'chirib, qayta qurish
TRIAL = [
    diagram([TALABA]),
    diagram([TALABA, GURUH]),
    diagram([TALABA]),
    diagram([TALABA, GURUH]),
    diagram([GURUH]),
    diagram([TALABA, GURUH]),
    diagram([TALABA]),
    diagram([TALABA, GURUH]),
    diagram([TALABA, GURUH, FAN], [relationship("r1", "t", "g")]),
]


class CurveTests(SimpleTestCase):
    def test_normalized_time(self):
        steps = [{"minutes": 0, "ratio": 0.0}, {"minutes": 5, "ratio": 0.5}, {"minutes": 10, "ratio": 1.0}]
        self.assertEqual(curve(steps, points=5), [0.0, 0.0, 0.5, 0.5, 1.0])
        self.assertEqual(curve([{"minutes": 0, "ratio": 0.4}], points=3), [0.4, 0.4, 0.4])


@override_settings(RESEARCH_CONSENT_REQUIRED=False)
class ProcessStatisticsTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.group_b.ai_enabled = False
        cls.group_b.save()
        cls.er_lab = Lab.objects.create(
            kind=Lab.Kind.ER, title="ER 1", description="d", reference_diagram=ER_REFERENCE, author=cls.teacher_a
        )
        cls.er_lab2 = Lab.objects.create(
            kind=Lab.Kind.ER, title="ER 2", description="d", reference_diagram=ER_REFERENCE, author=cls.teacher_a
        )
        for lab in (cls.er_lab, cls.er_lab2):
            lab.groups.add(cls.group_a, cls.group_b)
        # Tajriba (A) guruhi: sinab ko'rish, nazorat (B): avval obyektlar; har birida 4 talaba
        cls.experimental = [cls.student_a1, cls.student_a2] + [cls.make_student(f"ea{index}", cls.group_a) for index in range(2)]
        cls.control = [cls.student_b] + [cls.make_student(f"nb{index}", cls.group_b) for index in range(3)]
        for student in cls.experimental:
            cls.record(cls.er_lab, student, TRIAL, grade=60)
        for student in cls.control:
            cls.record(cls.er_lab, student, ENTITIES_FIRST, grade=100)
        # Birinchi talaba ikkinchi laboratoriyada strategiyasini o'zgartirgan
        cls.record(cls.er_lab2, cls.student_a1, ENTITIES_FIRST, grade=100, offset=timedelta(days=1))

    @staticmethod
    def make_student(username, group):
        return User.objects.create_user(username, password=PASSWORD, role=User.Role.STUDENT, group=group)

    @staticmethod
    def record(lab, student, sequence, grade, offset=timedelta()):
        """Oraliq holatlar har daqiqada, oxirgisi topshirish."""
        for index, item in enumerate(sequence[:-1]):
            snapshot = ErSnapshot.objects.create(lab=lab, student=student, diagram=item)
            ErSnapshot.objects.filter(pk=snapshot.pk).update(created_at=START + offset + timedelta(minutes=index))
        attempt = LabAttempt.objects.create(
            lab=lab, student=student, diagram=sequence[-1], is_correct=grade == 100, is_submission=True
        )
        LabAttempt.objects.filter(pk=attempt.pk).update(created_at=START + offset + timedelta(minutes=len(sequence)))
        LabGrade.objects.create(lab=lab, student=student, attempt=attempt, score=grade)

    def get(self, user, **params):
        # Login cheklovi (minutiga 5) bir testdagi ko'p foydalanuvchiga yetmaydi
        self.client.force_authenticate(user)
        return self.client.get(URL, params)

    def test_strategies_and_cohorts(self):
        response = self.get(self.admin)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        data = response.data
        self.assertEqual(data["works"], 9)
        self.assertEqual(data["students"], 8)
        items = {item["strategy"]: item for item in data["strategies"]["items"]}
        self.assertEqual(items["sinab_korish"]["count"], 4)
        self.assertEqual(items["avval_obyektlar"]["count"], 5)
        self.assertEqual(items["sinab_korish"]["mean_grade"], 60)
        self.assertEqual(items["avval_obyektlar"]["solved_rate"], 1.0)
        self.assertEqual(items["sinab_korish"]["by_cohort"], {"experimental": 4, "control": 0})
        self.assertTrue(data["strategies"]["cohort_test"]["significant"])

        curves = data["cohort_comparison"]["curves"]
        self.assertEqual(curves["experimental"]["n"], 5)
        self.assertEqual(curves["control"]["n"], 4)
        self.assertEqual(curves["control"]["points"][-1], 1.0)
        self.assertEqual(len(curves["control"]["points"]), 21)

        comparisons = {item["metric"]: item for item in data["cohort_comparison"]["comparisons"]}
        churn = comparisons["churn"]
        self.assertEqual(churn["experimental"]["n"], 4)  # bitta talaba — bitta kuzatuv
        self.assertGreater(churn["experimental"]["mean"], churn["control"]["mean"])
        self.assertIsNotNone(churn["test"])

        transitions = data["transitions"]
        self.assertEqual(transitions["students"], 1)
        keys = [item["strategy"] for item in transitions["strategies"]]
        self.assertEqual(transitions["matrix"][keys.index("sinab_korish")][keys.index("avval_obyektlar")], 1)
        self.assertTrue(data["conclusions"])

    def test_filters_and_access(self):
        data = self.get(self.admin, lab=self.er_lab2.pk).data
        self.assertEqual(data["works"], 1)
        self.assertEqual(len(data["labs"]), 2)
        data = self.get(self.admin, group=self.group_b.pk).data
        self.assertEqual(data["works"], 4)
        self.assertEqual(self.get(self.admin, lab="x").status_code, status.HTTP_400_BAD_REQUEST)
        # O'qituvchi faqat o'zi o'qitadigan guruhni ko'radi
        self.assertEqual(self.get(self.teacher_a).data["works"], 5)
        self.assertEqual(self.get(self.teacher_a, group=self.group_b.pk).status_code, status.HTTP_404_NOT_FOUND)
        # Boshqa o'qituvchi: laboratoriyalar uniki emas
        self.assertEqual(self.get(self.teacher_b).data["works"], 0)
        self.assertEqual(self.get(self.student_a1).status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(RESEARCH_CONSENT_REQUIRED=True)
    def test_only_consenting_students(self):
        self.student_b.research_consent = True
        self.student_b.save(update_fields=["research_consent"])
        data = self.get(self.admin).data
        self.assertEqual(data["works"], 1)
        self.assertIsNone(data["strategies"]["cohort_test"])
