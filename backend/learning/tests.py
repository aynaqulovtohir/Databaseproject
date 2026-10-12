"""Materiallar va topshiriqlar: ruxsatlar va tekshiruvlar testlari."""
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import StudentGroup, User

from .models import Assignment, Material, MaterialFile

PASSWORD = "Kuchli-Parol-2026"
TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="test_media_")
PDF_BYTES = b"%PDF-1.4 test fayl"


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class BaseTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.group_a = StudentGroup.objects.create(name="A-guruh")
        cls.group_b = StudentGroup.objects.create(name="B-guruh")
        cls.admin = User.objects.create_user("admin1", password=PASSWORD, role=User.Role.ADMIN)
        cls.teacher_a = User.objects.create_user(
            "teacher_a", password=PASSWORD, role=User.Role.TEACHER, first_name="Anvar"
        )
        cls.teacher_b = User.objects.create_user("teacher_b", password=PASSWORD, role=User.Role.TEACHER)
        cls.student_a = User.objects.create_user(
            "student_a", password=PASSWORD, role=User.Role.STUDENT, group=cls.group_a
        )
        cls.student_b = User.objects.create_user(
            "student_b", password=PASSWORD, role=User.Role.STUDENT, group=cls.group_b
        )
        cls.student_no_group = User.objects.create_user(
            "student_x", password=PASSWORD, role=User.Role.STUDENT
        )
        cls.group_a.teachers.add(cls.teacher_a)
        cls.group_b.teachers.add(cls.teacher_b)

        cls.material_a = Material.objects.create(title="Normallashtirish", text="1NF, 2NF, 3NF", author=cls.teacher_a)
        cls.material_a.groups.add(cls.group_a)
        cls.assignment_a = Assignment.objects.create(
            title="Kutubxona bazasi",
            description="Kutubxona uchun baza loyihalang",
            grading_criteria="Kamida 4 ta jadval, 3NF",
            author=cls.teacher_a,
            deadline=timezone.now() + timedelta(days=7),
        )
        cls.assignment_a.groups.add(cls.group_a)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        cache.clear()

    def auth_as(self, user):
        response = self.client.post("/api/auth/login/", {"username": user.username, "password": PASSWORD})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def upload(self, material, name="dars.pdf", content=PDF_BYTES):
        return self.client.post(
            f"/api/materials/{material.pk}/files/",
            {"file": SimpleUploadedFile(name, content)},
            format="multipart",
        )

    def future(self, days=3):
        return (timezone.now() + timedelta(days=days)).isoformat()


class MaterialVisibilityTests(BaseTestCase):
    def test_anonymous_rejected(self):
        self.assertEqual(self.client.get("/api/materials/").status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get("/api/assignments/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student_sees_only_own_group_material(self):
        self.auth_as(self.student_a)
        response = self.client.get("/api/materials/")
        self.assertEqual([item["id"] for item in response.data], [self.material_a.pk])
        self.assertNotIn("groups", response.data[0])

    def test_other_group_student_sees_nothing(self):
        self.auth_as(self.student_b)
        self.assertEqual(self.client.get("/api/materials/").data, [])
        self.assertEqual(
            self.client.get(f"/api/materials/{self.material_a.pk}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_student_without_group_sees_nothing(self):
        self.auth_as(self.student_no_group)
        self.assertEqual(self.client.get("/api/materials/").data, [])
        self.assertEqual(self.client.get("/api/assignments/").data, [])

    def test_teacher_does_not_see_other_teachers_material(self):
        self.auth_as(self.teacher_b)
        self.assertEqual(self.client.get("/api/materials/").data, [])
        self.assertEqual(
            self.client.patch(f"/api/materials/{self.material_a.pk}/", {"title": "x"}).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.delete(f"/api/materials/{self.material_a.pk}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_admin_sees_all(self):
        self.auth_as(self.admin)
        self.assertEqual(len(self.client.get("/api/materials/").data), 1)
        self.assertEqual(len(self.client.get("/api/assignments/").data), 1)


class MaterialManagementTests(BaseTestCase):
    def test_teacher_creates_material_for_own_group(self):
        self.auth_as(self.teacher_a)
        response = self.client.post(
            "/api/materials/",
            {"title": "ER model", "text": "Mohiyat va bog'lanish", "groups": [self.group_a.pk]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["author"]["id"], self.teacher_a.pk)

    def test_teacher_cannot_use_foreign_group(self):
        self.auth_as(self.teacher_a)
        response = self.client.post(
            "/api/materials/", {"title": "ER model", "groups": [self.group_b.pk]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("groups", response.data)

    def test_groups_required(self):
        self.auth_as(self.teacher_a)
        response = self.client.post("/api/materials/", {"title": "ER model", "groups": []}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_use_any_group(self):
        self.auth_as(self.admin)
        response = self.client.post(
            "/api/materials/",
            {"title": "Umumiy", "groups": [self.group_a.pk, self.group_b.pk]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_student_cannot_create_edit_or_delete(self):
        self.auth_as(self.student_a)
        url = f"/api/materials/{self.material_a.pk}/"
        self.assertEqual(
            self.client.post("/api/materials/", {"title": "x", "groups": [self.group_a.pk]}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(self.client.patch(url, {"title": "x"}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_403_FORBIDDEN)

    def test_author_cannot_be_spoofed(self):
        self.auth_as(self.teacher_a)
        response = self.client.post(
            "/api/materials/",
            {"title": "x", "groups": [self.group_a.pk], "author": self.teacher_b.pk},
            format="json",
        )
        self.assertEqual(response.data["author"]["id"], self.teacher_a.pk)


class MaterialFileTests(BaseTestCase):
    def test_upload_and_download(self):
        self.auth_as(self.teacher_a)
        response = self.upload(self.material_a)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["original_name"], "dars.pdf")
        file_id = response.data["id"]
        # Diskda asl nom bilan emas, tasodifiy nom bilan saqlanadi
        self.assertNotIn("dars", MaterialFile.objects.get(pk=file_id).file.name)

        self.auth_as(self.student_a)
        download = self.client.get(f"/api/materials/files/{file_id}/download/")
        self.assertEqual(download.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(download.streaming_content), PDF_BYTES)
        self.assertIn("attachment", download["Content-Disposition"])

    def test_download_denied_for_others(self):
        self.auth_as(self.teacher_a)
        file_id = self.upload(self.material_a).data["id"]
        url = f"/api/materials/files/{file_id}/download/"

        for user in (self.student_b, self.student_no_group, self.teacher_b):
            self.auth_as(user)
            self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND, user.username)

        self.client.credentials()
        self.assertEqual(self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_public_media_url(self):
        self.auth_as(self.teacher_a)
        file_id = self.upload(self.material_a).data["id"]
        stored_name = MaterialFile.objects.get(pk=file_id).file.name
        self.client.credentials()
        self.assertEqual(self.client.get(f"/media/{stored_name}").status_code, status.HTTP_404_NOT_FOUND)

    def test_wrong_extension_rejected(self):
        self.auth_as(self.teacher_a)
        response = self.upload(self.material_a, name="virus.exe", content=b"MZ....")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_fake_extension_rejected(self):
        self.auth_as(self.teacher_a)
        response = self.upload(self.material_a, name="rasm.png", content=b"<script>alert(1)</script>")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_too_large_rejected(self):
        self.auth_as(self.teacher_a)
        response = self.upload(self.material_a, content=b"%PDF" + b"0" * (20 * 1024 * 1024))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_student_and_foreign_teacher_cannot_upload(self):
        self.auth_as(self.student_a)
        self.assertEqual(self.upload(self.material_a).status_code, status.HTTP_403_FORBIDDEN)
        self.auth_as(self.teacher_b)
        self.assertEqual(self.upload(self.material_a).status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_file_removes_it_from_disk(self):
        self.auth_as(self.teacher_a)
        file_id = self.upload(self.material_a).data["id"]
        path = Path(MaterialFile.objects.get(pk=file_id).file.path)
        self.assertTrue(path.exists())

        self.auth_as(self.student_a)
        self.assertEqual(
            self.client.delete(f"/api/materials/files/{file_id}/").status_code, status.HTTP_403_FORBIDDEN
        )
        self.auth_as(self.teacher_b)
        self.assertEqual(
            self.client.delete(f"/api/materials/files/{file_id}/").status_code, status.HTTP_404_NOT_FOUND
        )
        self.assertTrue(path.exists())

        self.auth_as(self.teacher_a)
        self.assertEqual(
            self.client.delete(f"/api/materials/files/{file_id}/").status_code, status.HTTP_204_NO_CONTENT
        )
        self.assertFalse(path.exists())

    def test_deleting_material_removes_its_files(self):
        self.auth_as(self.teacher_a)
        file_id = self.upload(self.material_a).data["id"]
        path = Path(MaterialFile.objects.get(pk=file_id).file.path)
        self.assertEqual(
            self.client.delete(f"/api/materials/{self.material_a.pk}/").status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertFalse(path.exists())


class AssignmentTests(BaseTestCase):
    def payload(self, **overrides):
        data = {
            "title": "Do'kon bazasi",
            "description": "Internet-do'kon uchun baza loyihalang",
            "grading_criteria": "Tashqi kalitlar bo'lishi shart",
            "groups": [self.group_a.pk],
            "deadline": self.future(),
        }
        data.update(overrides)
        return data

    def test_student_view_hides_criteria_and_groups(self):
        self.auth_as(self.student_a)
        response = self.client.get("/api/assignments/")
        self.assertEqual(len(response.data), 1)
        self.assertNotIn("grading_criteria", response.data[0])
        self.assertNotIn("groups", response.data[0])
        detail = self.client.get(f"/api/assignments/{self.assignment_a.pk}/")
        self.assertNotIn("grading_criteria", detail.data)
        self.assertEqual(detail.data["author"]["first_name"], "Anvar")

    def test_other_group_student_cannot_see(self):
        self.auth_as(self.student_b)
        self.assertEqual(self.client.get("/api/assignments/").data, [])
        self.assertEqual(
            self.client.get(f"/api/assignments/{self.assignment_a.pk}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_teacher_sees_criteria_of_own_assignment(self):
        self.auth_as(self.teacher_a)
        response = self.client.get(f"/api/assignments/{self.assignment_a.pk}/")
        self.assertEqual(response.data["grading_criteria"], "Kamida 4 ta jadval, 3NF")

    def test_teacher_creates_assignment(self):
        self.auth_as(self.teacher_a)
        response = self.client.post("/api/assignments/", self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["author"]["id"], self.teacher_a.pk)

    def test_teacher_cannot_assign_to_foreign_group(self):
        self.auth_as(self.teacher_a)
        response = self.client.post(
            "/api/assignments/", self.payload(groups=[self.group_a.pk, self.group_b.pk]), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("groups", response.data)

    def test_deadline_required_and_must_be_future(self):
        self.auth_as(self.teacher_a)
        payload = self.payload()
        del payload["deadline"]
        self.assertEqual(
            self.client.post("/api/assignments/", payload, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        response = self.client.post("/api/assignments/", self.payload(deadline=self.future(-1)), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("deadline", response.data)

    def test_edit_title_after_deadline_passed(self):
        Assignment.objects.filter(pk=self.assignment_a.pk).update(deadline=timezone.now() - timedelta(days=1))
        self.auth_as(self.teacher_a)
        response = self.client.patch(
            f"/api/assignments/{self.assignment_a.pk}/", {"title": "Yangi nom"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    def test_teacher_cannot_touch_other_teachers_assignment(self):
        self.auth_as(self.teacher_b)
        url = f"/api/assignments/{self.assignment_a.pk}/"
        self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.patch(url, {"title": "x"}).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_404_NOT_FOUND)

    def test_student_cannot_create_edit_or_delete(self):
        self.auth_as(self.student_a)
        url = f"/api/assignments/{self.assignment_a.pk}/"
        self.assertEqual(
            self.client.post("/api/assignments/", self.payload(), format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(self.client.patch(url, {"title": "x"}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_manages_any_assignment(self):
        self.auth_as(self.admin)
        url = f"/api/assignments/{self.assignment_a.pk}/"
        self.assertEqual(self.client.patch(url, {"title": "Admin tahriri"}).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_204_NO_CONTENT)


class TeacherDeletionTests(BaseTestCase):
    def test_teacher_with_content_cannot_be_deleted(self):
        self.auth_as(self.admin)
        response = self.client.delete(f"/api/users/{self.teacher_a.pk}/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.filter(pk=self.teacher_a.pk).exists())
        self.assertTrue(Material.objects.filter(pk=self.material_a.pk).exists())
