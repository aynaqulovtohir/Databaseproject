"""Baholash va qayta ishlashga qaytarish testlari."""
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from ai.models import AIAnalysis
from learning.models import Assignment
from submissions.models import Submission
from users.models import StudentGroup, User

from .models import Grade

PASSWORD = "Kuchli-Parol-2026"
SQL = "CREATE TABLE kitob (id SERIAL PRIMARY KEY);"


class BaseTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.group = StudentGroup.objects.create(name="A-guruh")
        cls.admin = User.objects.create_user("admin1", password=PASSWORD, role=User.Role.ADMIN)
        cls.teacher = User.objects.create_user(
            "teacher_a", password=PASSWORD, role=User.Role.TEACHER, first_name="Anvar"
        )
        cls.other_teacher = User.objects.create_user("teacher_b", password=PASSWORD, role=User.Role.TEACHER)
        cls.student = User.objects.create_user(
            "student1", password=PASSWORD, role=User.Role.STUDENT, group=cls.group
        )
        cls.classmate = User.objects.create_user(
            "student2", password=PASSWORD, role=User.Role.STUDENT, group=cls.group
        )
        cls.group.teachers.add(cls.teacher)
        cls.assignment = Assignment.objects.create(
            title="Kutubxona bazasi",
            description="Baza loyihalang",
            author=cls.teacher,
            deadline=timezone.now() + timedelta(days=7),
        )
        cls.assignment.groups.add(cls.group)

    def setUp(self):
        cache.clear()
        self.submission = Submission.objects.create(
            assignment=self.assignment, student=self.student, sql_code=SQL, attempt_number=1
        )
        self.grade_url = f"/api/submissions/{self.submission.pk}/grade/"
        self.return_url = f"/api/submissions/{self.submission.pk}/return/"
        self.submit_url = f"/api/assignments/{self.assignment.pk}/submissions/"

    def auth_as(self, user):
        response = self.client.post("/api/auth/login/", {"username": user.username, "password": PASSWORD})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def grade(self, score=85, comment="Yaxshi ish", url=None):
        return self.client.put(url or self.grade_url, {"score": score, "comment": comment}, format="json")

    def set_ai_score(self, score=70):
        AIAnalysis.objects.filter(submission=self.submission).update(
            status=AIAnalysis.Status.DONE, suggested_score=score
        )


class GradeTests(BaseTestCase):
    def test_teacher_grades(self):
        self.set_ai_score(70)
        self.auth_as(self.teacher)
        response = self.grade()
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["status"], "graded")
        self.assertEqual(response.data["grade"]["score"], 85)
        self.assertEqual(response.data["grade"]["comment"], "Yaxshi ish")
        self.assertEqual(response.data["grade"]["ai_suggested_score"], 70)
        self.assertEqual(response.data["grade"]["graded_by"]["id"], self.teacher.pk)

    def test_grading_without_ai_analysis(self):
        self.auth_as(self.teacher)
        response = self.grade()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["grade"]["ai_suggested_score"])

    def test_comment_is_optional(self):
        self.auth_as(self.teacher)
        response = self.client.put(self.grade_url, {"score": 90}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["grade"]["comment"], "")

    def test_teacher_can_change_grade(self):
        self.auth_as(self.teacher)
        self.grade(60)
        response = self.grade(75, "Qayta ko'rib chiqdim")
        self.assertEqual(response.data["grade"]["score"], 75)
        self.assertEqual(Grade.objects.count(), 1)

    def test_ai_score_is_filled_on_later_edit(self):
        self.auth_as(self.teacher)
        self.grade(60)
        self.set_ai_score(55)
        self.assertEqual(self.grade(65).data["grade"]["ai_suggested_score"], 55)
        # Bir marta saqlangan AI taklifi keyin o'zgarmaydi
        self.set_ai_score(99)
        self.assertEqual(self.grade(66).data["grade"]["ai_suggested_score"], 55)

    def test_score_validation(self):
        self.auth_as(self.teacher)
        for bad in (-1, 101, "abc", 85.5, None):
            response = self.client.put(self.grade_url, {"score": bad}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, bad)
        self.assertEqual(self.client.put(self.grade_url, {}, format="json").status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.grade(0).status_code, status.HTTP_200_OK)
        self.assertEqual(self.grade(100).status_code, status.HTTP_200_OK)

    def test_admin_can_grade(self):
        self.auth_as(self.admin)
        self.assertEqual(self.grade().status_code, status.HTTP_200_OK)

    def test_students_cannot_grade(self):
        for user in (self.student, self.classmate):
            self.auth_as(user)
            self.assertEqual(self.grade(100).status_code, status.HTTP_403_FORBIDDEN, user.username)
            self.assertEqual(
                self.client.post(self.return_url, {"comment": "x"}, format="json").status_code,
                status.HTTP_403_FORBIDDEN,
            )
        self.assertEqual(Grade.objects.count(), 0)

    def test_other_teacher_cannot_grade(self):
        self.auth_as(self.other_teacher)
        self.assertEqual(self.grade().status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.post(self.return_url, {"comment": "x"}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_anonymous_rejected(self):
        self.assertEqual(self.grade().status_code, status.HTTP_401_UNAUTHORIZED)

    def test_only_latest_attempt_can_be_graded(self):
        newer = Submission.objects.create(
            assignment=self.assignment, student=self.student, sql_code=SQL, attempt_number=2
        )
        self.auth_as(self.teacher)
        self.assertEqual(self.grade().status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            self.grade(url=f"/api/submissions/{newer.pk}/grade/").status_code, status.HTTP_200_OK
        )

    def test_graded_blocks_student_resubmit(self):
        self.auth_as(self.teacher)
        self.grade()
        self.auth_as(self.student)
        response = self.client.post(self.submit_url, {"sql_code": SQL}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class VisibilityTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.set_ai_score(70)
        self.auth_as(self.teacher)
        self.grade(85, "Yaxshi ish")
        self.detail_url = f"/api/submissions/{self.submission.pk}/"

    def test_student_sees_own_grade_without_ai_score(self):
        self.auth_as(self.student)
        for data in (self.client.get(self.detail_url).data, self.client.get(self.submit_url).data[0]):
            self.assertEqual(data["grade"]["score"], 85)
            self.assertEqual(data["grade"]["comment"], "Yaxshi ish")
            self.assertNotIn("ai_suggested_score", data["grade"])
            self.assertNotIn("graded_by", data["grade"])

    def test_classmate_cannot_see_grade(self):
        self.auth_as(self.classmate)
        self.assertEqual(self.client.get(self.detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(self.submit_url).data, [])

    def test_teacher_list_shows_grade_with_ai_score(self):
        self.auth_as(self.teacher)
        data = self.client.get(self.submit_url).data
        self.assertEqual(data[0]["grade"]["ai_suggested_score"], 70)

    def test_ungraded_submission_has_null_grade(self):
        other = Submission.objects.create(
            assignment=self.assignment, student=self.classmate, sql_code=SQL, attempt_number=1
        )
        self.auth_as(self.teacher)
        self.assertIsNone(self.client.get(f"/api/submissions/{other.pk}/").data["grade"])


class ReturnTests(BaseTestCase):
    def give_back(self, comment="Tashqi kalitlarni qo'shing"):
        return self.client.post(self.return_url, {"comment": comment}, format="json")

    def test_return_requires_comment(self):
        self.auth_as(self.teacher)
        self.assertEqual(self.give_back("").status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.post(self.return_url, {}, format="json").status_code, status.HTTP_400_BAD_REQUEST)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, "submitted")

    def test_return_without_grade(self):
        self.auth_as(self.teacher)
        response = self.give_back()
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["status"], "returned")
        self.assertEqual(response.data["return_comment"], "Tashqi kalitlarni qo'shing")
        self.assertIsNone(response.data["grade"])

    def test_full_cycle_keeps_history(self):
        self.auth_as(self.teacher)
        self.grade(60, "Kamchiliklar bor")
        self.give_back()
        self.assertEqual(self.give_back().status_code, status.HTTP_400_BAD_REQUEST)

        self.auth_as(self.student)
        second = self.client.post(self.submit_url, {"sql_code": SQL + " -- v2"}, format="json")
        self.assertEqual(second.status_code, status.HTTP_201_CREATED, second.data)
        self.assertEqual(second.data["attempt_number"], 2)
        self.assertIsNone(second.data["grade"])
        self.assertEqual(second.data["return_comment"], "")

        self.auth_as(self.teacher)
        # Eski urinishni endi baholab yoki qaytarib bo'lmaydi
        self.assertEqual(self.grade(100).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.grade(85, url=f"/api/submissions/{second.data['id']}/grade/").status_code, status.HTTP_200_OK)

        self.auth_as(self.student)
        attempts = self.client.get(self.submit_url).data
        self.assertEqual(
            [(a["attempt_number"], a["status"], a["grade"]["score"]) for a in attempts],
            [(2, "graded", 85), (1, "returned", 60)],
        )
        self.assertEqual(attempts[1]["return_comment"], "Tashqi kalitlarni qo'shing")

    def test_returned_submission_can_be_graded_instead(self):
        self.auth_as(self.teacher)
        self.give_back()
        response = self.grade(70)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "graded")
