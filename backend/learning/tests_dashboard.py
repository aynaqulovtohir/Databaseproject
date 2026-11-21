"""Bosh sahifa ko'rsatkichlari: har bir rol faqat o'ziga ruxsat etilgan ma'lumotni ko'radi."""
from datetime import timedelta

from django.utils import timezone
from rest_framework import status

from grading.models import Grade
from labs.models import Lab, LabAttempt
from submissions.models import Submission

from .dashboard import CHART_DAYS
from .models import Assignment
from .tests import BaseTestCase

URL = "/api/dashboard/"


def cards(response):
    return {card["key"]: card for card in response.data["cards"]}


class DashboardTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.lab_a = Lab.objects.create(title="A laboratoriya", description="x", setup_sql="", author=cls.teacher_a)
        cls.lab_a.groups.add(cls.group_a)
        cls.lab_b = Lab.objects.create(title="B laboratoriya", description="x", setup_sql="", author=cls.teacher_b)
        cls.lab_b.groups.add(cls.group_b)
        cls.assignment_b = Assignment.objects.create(
            title="Maxfiy B topshiriq",
            description="x",
            author=cls.teacher_b,
            deadline=timezone.now() + timedelta(days=2),
        )
        cls.assignment_b.groups.add(cls.group_b)
        cls.sub_a = Submission.objects.create(
            assignment=cls.assignment_a, student=cls.student_a, sql_code="SELECT 1;", attempt_number=1
        )
        cls.sub_b = Submission.objects.create(
            assignment=cls.assignment_b, student=cls.student_b, sql_code="SELECT 'maxfiy';", attempt_number=1
        )
        LabAttempt.objects.create(lab=cls.lab_a, student=cls.student_a, sql_code="SELECT 1;", is_correct=True)
        LabAttempt.objects.create(lab=cls.lab_b, student=cls.student_b, sql_code="SELECT 'maxfiy';", is_correct=False)

    def test_requires_login(self):
        self.assertEqual(self.client.get(URL).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student_sees_only_own_data(self):
        self.auth_as(self.student_a)
        response = self.client.get(URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = cards(response)
        self.assertEqual(data["assignments"]["value"], "1/1")
        self.assertEqual(data["labs"]["value"], "1/1")
        titles = {item["title"] for item in response.data["recent"]}
        self.assertEqual(titles, {"Kutubxona bazasi", "A laboratoriya"})
        # Talabaga boshqalarning ismi ko'rsatilmaydi
        self.assertTrue(all(item["actor"] is None for item in response.data["recent"]))
        body = str(response.data)
        self.assertNotIn("maxfiy", body.lower())
        self.assertNotIn("SELECT", body)

    def test_student_alerts_upcoming_and_returned(self):
        self.auth_as(self.student_b)
        alerts = self.client.get(URL).data["alerts"]
        # B topshiriq yechilgan: muddat eslatmasi yo'q
        self.assertEqual(alerts, [])
        Submission.objects.filter(pk=self.sub_b.pk).update(status=Submission.Status.RETURNED)
        alerts = self.client.get(URL).data["alerts"]
        self.assertEqual([(a["tone"], a["title"]) for a in alerts], [("danger", "Maxfiy B topshiriq")])

    def test_student_without_submission_gets_deadline_alert(self):
        Submission.objects.filter(pk=self.sub_a.pk).delete()
        Assignment.objects.filter(pk=self.assignment_a.pk).update(deadline=timezone.now() + timedelta(days=1))
        self.auth_as(self.student_a)
        alerts = self.client.get(URL).data["alerts"]
        self.assertEqual([a["title"] for a in alerts], ["Kutubxona bazasi"])

    def test_average_grade(self):
        Grade.objects.create(submission=self.sub_a, score=80, graded_by=self.teacher_a)
        self.auth_as(self.student_a)
        self.assertEqual(cards(self.client.get(URL))["grade"]["value"], 80)

    def test_teacher_sees_only_own_scope(self):
        self.auth_as(self.teacher_a)
        response = self.client.get(URL)
        data = cards(response)
        self.assertEqual(data["students"]["value"], 1)
        self.assertEqual(data["pending"]["value"], 1)
        self.assertEqual(data["labs"]["value"], 1)
        self.assertNotIn("Maxfiy B topshiriq", str(response.data))
        self.assertNotIn("B laboratoriya", str(response.data))
        self.assertEqual([a["link"] for a in response.data["alerts"]], [f"/submissions/{self.sub_a.pk}"])

    def test_admin_sees_everything(self):
        self.auth_as(self.admin)
        response = self.client.get(URL)
        data = cards(response)
        self.assertEqual(data["pending"]["value"], 2)
        self.assertEqual(data["labs"]["value"], 2)
        self.assertEqual(data["groups"]["value"], 2)

    def test_chart_has_fixed_window(self):
        self.auth_as(self.admin)
        chart = self.client.get(URL).data["chart"]
        self.assertEqual(len(chart["days"]), CHART_DAYS)
        self.assertEqual(chart["days"][-1], timezone.localdate().isoformat())
        self.assertEqual(sum(chart["series"]["submissions"]), 2)
        self.assertEqual(sum(chart["series"]["lab_attempts"]), 2)
        for values in chart["series"].values():
            self.assertEqual(len(values), CHART_DAYS)
