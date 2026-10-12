"""Yechim topshirish: ruxsatlar va qoidalar testlari."""
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from learning.models import Assignment
from users.models import StudentGroup, User

from .models import Submission

PASSWORD = "Kuchli-Parol-2026"
SQL = "CREATE TABLE kitob (id SERIAL PRIMARY KEY, nomi VARCHAR(200) NOT NULL);"


class BaseTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.group_a = StudentGroup.objects.create(name="A-guruh")
        cls.group_b = StudentGroup.objects.create(name="B-guruh")
        cls.admin = User.objects.create_user("admin1", password=PASSWORD, role=User.Role.ADMIN)
        cls.teacher_a = User.objects.create_user("teacher_a", password=PASSWORD, role=User.Role.TEACHER)
        cls.teacher_b = User.objects.create_user("teacher_b", password=PASSWORD, role=User.Role.TEACHER)
        cls.student_a1 = User.objects.create_user(
            "student_a1", password=PASSWORD, role=User.Role.STUDENT, group=cls.group_a, first_name="Ali"
        )
        cls.student_a2 = User.objects.create_user(
            "student_a2", password=PASSWORD, role=User.Role.STUDENT, group=cls.group_a
        )
        cls.student_b = User.objects.create_user(
            "student_b", password=PASSWORD, role=User.Role.STUDENT, group=cls.group_b
        )
        cls.group_a.teachers.add(cls.teacher_a)
        cls.group_b.teachers.add(cls.teacher_b)
        cls.assignment = Assignment.objects.create(
            title="Kutubxona bazasi",
            description="Kutubxona uchun baza loyihalang",
            author=cls.teacher_a,
            deadline=timezone.now() + timedelta(days=7),
        )
        cls.assignment.groups.add(cls.group_a)
        cls.url = f"/api/assignments/{cls.assignment.pk}/submissions/"

    def setUp(self):
        cache.clear()

    def auth_as(self, user):
        response = self.client.post("/api/auth/login/", {"username": user.username, "password": PASSWORD})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def submit(self, sql_code=SQL):
        return self.client.post(self.url, {"sql_code": sql_code}, format="json")


class SubmitTests(BaseTestCase):
    def test_student_submits(self):
        self.auth_as(self.student_a1)
        response = self.submit()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["attempt_number"], 1)
        self.assertEqual(response.data["status"], "submitted")
        self.assertFalse(response.data["is_late"])
        self.assertEqual(response.data["sql_code"], SQL)
        self.assertEqual(response.data["student"]["id"], self.student_a1.pk)

    def test_resubmit_keeps_every_attempt(self):
        self.auth_as(self.student_a1)
        self.submit("CREATE TABLE a (id INT);")
        response = self.submit("CREATE TABLE b (id INT);")
        self.assertEqual(response.data["attempt_number"], 2)
        attempts = self.client.get(self.url).data
        self.assertEqual([item["attempt_number"] for item in attempts], [2, 1])

    def test_late_submission_is_marked(self):
        Assignment.objects.filter(pk=self.assignment.pk).update(deadline=timezone.now() - timedelta(hours=1))
        self.auth_as(self.student_a1)
        response = self.submit()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["is_late"])

    def test_graded_blocks_resubmit_and_returned_allows(self):
        self.auth_as(self.student_a1)
        submission_id = self.submit().data["id"]

        Submission.objects.filter(pk=submission_id).update(status=Submission.Status.GRADED)
        self.assertEqual(self.submit().status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Submission.objects.count(), 1)

        Submission.objects.filter(pk=submission_id).update(status=Submission.Status.RETURNED)
        response = self.submit()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["attempt_number"], 2)

    def test_empty_and_too_long_code_rejected(self):
        self.auth_as(self.student_a1)
        self.assertEqual(self.submit("").status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.submit("   \n  ").status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.post(self.url, {}, format="json").status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.submit("x" * 50_001).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.submit("x" * 50_000).status_code, status.HTTP_201_CREATED)

    def test_other_group_student_cannot_submit(self):
        self.auth_as(self.student_b)
        self.assertEqual(self.submit().status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Submission.objects.count(), 0)

    def test_teacher_and_admin_cannot_submit(self):
        for user in (self.teacher_a, self.admin):
            self.auth_as(user)
            self.assertEqual(self.submit().status_code, status.HTTP_403_FORBIDDEN, user.username)

    def test_anonymous_rejected(self):
        self.assertEqual(self.submit().status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student_cannot_spoof_fields(self):
        self.auth_as(self.student_a1)
        response = self.client.post(
            self.url,
            {"sql_code": SQL, "student": self.student_a2.pk, "status": "graded", "attempt_number": 99, "is_late": True},
            format="json",
        )
        self.assertEqual(response.data["student"]["id"], self.student_a1.pk)
        self.assertEqual(response.data["status"], "submitted")
        self.assertEqual(response.data["attempt_number"], 1)
        self.assertFalse(response.data["is_late"])

    def test_submission_cannot_be_edited_or_deleted(self):
        self.auth_as(self.student_a1)
        submission_id = self.submit().data["id"]
        url = f"/api/submissions/{submission_id}/"
        self.assertEqual(self.client.patch(url, {"sql_code": "x"}).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class VisibilityTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.first = Submission.objects.create(
            assignment=self.assignment, student=self.student_a1, sql_code="CREATE TABLE a1_v1 (id INT);", attempt_number=1
        )
        self.second = Submission.objects.create(
            assignment=self.assignment, student=self.student_a1, sql_code="CREATE TABLE a1_v2 (id INT);", attempt_number=2
        )
        self.other = Submission.objects.create(
            assignment=self.assignment, student=self.student_a2, sql_code="CREATE TABLE a2_v1 (id INT);", attempt_number=1
        )

    def test_student_sees_only_own_attempts(self):
        self.auth_as(self.student_a1)
        data = self.client.get(self.url).data
        self.assertEqual({item["id"] for item in data}, {self.first.pk, self.second.pk})

    def test_student_cannot_open_classmates_submission(self):
        self.auth_as(self.student_a1)
        self.assertEqual(
            self.client.get(f"/api/submissions/{self.other.pk}/").status_code, status.HTTP_404_NOT_FOUND
        )
        self.assertEqual(self.client.get(f"/api/submissions/{self.first.pk}/").status_code, status.HTTP_200_OK)

    def test_student_filter_param_does_not_leak(self):
        self.auth_as(self.student_a1)
        data = self.client.get(self.url, {"student": self.student_a2.pk}).data
        self.assertTrue(all(item["student"]["id"] == self.student_a1.pk for item in data))

    def test_teacher_sees_latest_attempt_per_student(self):
        self.auth_as(self.teacher_a)
        data = self.client.get(self.url).data
        self.assertEqual({item["id"] for item in data}, {self.second.pk, self.other.pk})

    def test_teacher_sees_all_attempts_of_one_student(self):
        self.auth_as(self.teacher_a)
        data = self.client.get(self.url, {"student": self.student_a1.pk}).data
        self.assertEqual([item["attempt_number"] for item in data], [2, 1])
        self.assertEqual(
            self.client.get(self.url, {"student": "abc"}).status_code, status.HTTP_400_BAD_REQUEST
        )

    def test_other_teacher_sees_nothing(self):
        self.auth_as(self.teacher_b)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.get(f"/api/submissions/{self.first.pk}/").status_code, status.HTTP_404_NOT_FOUND
        )

    def test_admin_sees_everything(self):
        self.auth_as(self.admin)
        self.assertEqual(len(self.client.get(self.url).data), 2)
        self.assertEqual(self.client.get(f"/api/submissions/{self.other.pk}/").status_code, status.HTTP_200_OK)


class DeletionRuleTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        Submission.objects.create(
            assignment=self.assignment, student=self.student_a1, sql_code=SQL, attempt_number=1
        )

    def test_assignment_with_submissions_cannot_be_deleted(self):
        self.auth_as(self.teacher_a)
        response = self.client.delete(f"/api/assignments/{self.assignment.pk}/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Assignment.objects.filter(pk=self.assignment.pk).exists())
        self.assertEqual(Submission.objects.count(), 1)

    def test_assignment_with_submissions_can_still_be_edited(self):
        self.auth_as(self.teacher_a)
        response = self.client.patch(f"/api/assignments/{self.assignment.pk}/", {"title": "Yangi nom"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_deleting_student_deletes_their_submissions(self):
        self.auth_as(self.admin)
        response = self.client.delete(f"/api/users/{self.student_a1.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Submission.objects.count(), 0)
