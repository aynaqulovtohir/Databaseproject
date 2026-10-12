"""Kirish va ruxsatlar testlari."""
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from .models import StudentGroup, User

PASSWORD = "Kuchli-Parol-2026"


class BaseTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.group = StudentGroup.objects.create(name="DB-101")
        cls.admin = User.objects.create_user("admin1", password=PASSWORD, role=User.Role.ADMIN)
        cls.teacher = User.objects.create_user("teacher1", password=PASSWORD, role=User.Role.TEACHER)
        cls.student = User.objects.create_user(
            "student1", password=PASSWORD, role=User.Role.STUDENT, group=cls.group
        )
        cls.group.teachers.add(cls.teacher)

    def setUp(self):
        # Login cheklovi hisoblagichi har bir testda noldan boshlansin
        cache.clear()

    def login(self, username, password=PASSWORD):
        return self.client.post("/api/auth/login/", {"username": username, "password": password})

    def auth_as(self, user):
        token = self.login(user.username).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class AuthTests(BaseTestCase):
    def test_login_returns_tokens(self):
        response = self.login("student1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        # Refresh token javob matnida emas, httpOnly cookie'da
        self.assertNotIn("refresh", response.data)
        cookie = response.cookies["refresh_token"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Strict")
        self.assertEqual(cookie["path"], "/api/auth/")

    def test_login_wrong_password(self):
        response = self.login("student1", "notogri-parol")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_blocked_user_cannot_login(self):
        User.objects.filter(pk=self.student.pk).update(is_active=False)
        response = self.login("student1")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_blocked_user_old_token_stops_working(self):
        self.auth_as(self.student)
        User.objects.filter(pk=self.student.pk).update(is_active=False)
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_uses_cookie(self):
        self.login("student1")
        response = self.client.post("/api/auth/refresh/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, status.HTTP_200_OK)

    def test_refresh_without_or_with_bad_cookie(self):
        self.assertEqual(self.client.post("/api/auth/refresh/").status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.cookies["refresh_token"] = "soxta-token"
        self.assertEqual(self.client.post("/api/auth/refresh/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token_in_body_is_ignored(self):
        self.login("student1")
        refresh = self.client.cookies["refresh_token"].value
        self.client.cookies.clear()
        response = self.client.post("/api/auth/refresh/", {"refresh": refresh})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_blocked_user_cannot_refresh(self):
        self.login("student1")
        User.objects.filter(pk=self.student.pk).update(is_active=False)
        self.assertEqual(self.client.post("/api/auth/refresh/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_access_token_cannot_be_used_as_refresh(self):
        access = self.login("student1").data["access"]
        self.client.cookies["refresh_token"] = access
        self.assertEqual(self.client.post("/api/auth/refresh/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_clears_cookie(self):
        self.login("student1")
        response = self.client.post("/api/auth/logout/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.cookies["refresh_token"].value, "")
        self.assertEqual(self.client.post("/api/auth/refresh/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_requires_login(self):
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_own_data_without_password(self):
        self.auth_as(self.student)
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "student1")
        self.assertEqual(response.data["role"], "student")
        self.assertEqual(response.data["group"], {"id": self.group.id, "name": "DB-101"})
        self.assertNotIn("password", response.data)

    def test_teacher_me_shows_teaching_groups(self):
        self.auth_as(self.teacher)
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.data["teaching_groups"], [{"id": self.group.id, "name": "DB-101"}])


class LoginThrottleTests(BaseTestCase):
    def test_sixth_attempt_in_a_minute_is_blocked(self):
        for _ in range(5):
            self.assertEqual(
                self.login("student1", "notogri-parol").status_code, status.HTTP_401_UNAUTHORIZED
            )
        # To'g'ri parol bilan ham vaqtincha kirib bo'lmaydi
        self.assertEqual(self.login("student1").status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class ChangePasswordTests(BaseTestCase):
    def test_change_password(self):
        self.auth_as(self.student)
        response = self.client.post(
            "/api/auth/change-password/",
            {"old_password": PASSWORD, "new_password": "Yangi-Parol-2026"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.login("student1", "Yangi-Parol-2026").status_code, status.HTTP_200_OK)
        self.assertEqual(self.login("student1", PASSWORD).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_wrong_old_password_rejected(self):
        self.auth_as(self.student)
        response = self.client.post(
            "/api/auth/change-password/",
            {"old_password": "notogri", "new_password": "Yangi-Parol-2026"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_weak_new_password_rejected(self):
        self.auth_as(self.student)
        response = self.client.post(
            "/api/auth/change-password/", {"old_password": PASSWORD, "new_password": "123"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserPermissionTests(BaseTestCase):
    def test_anonymous_cannot_list_users(self):
        self.assertEqual(self.client.get("/api/users/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student_cannot_access_users_or_groups(self):
        self.auth_as(self.student)
        self.assertEqual(self.client.get("/api/users/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get("/api/groups/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.get(f"/api/users/{self.teacher.pk}/").status_code, status.HTTP_403_FORBIDDEN
        )

    def test_teacher_cannot_access_users_or_groups(self):
        self.auth_as(self.teacher)
        self.assertEqual(self.client.get("/api/users/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get("/api/groups/").status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_create_user_or_make_self_admin(self):
        self.auth_as(self.student)
        response = self.client.post(
            "/api/users/", {"username": "x", "password": PASSWORD, "role": "admin"}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.patch(f"/api/users/{self.student.pk}/", {"role": "admin"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.student.refresh_from_db()
        self.assertEqual(self.student.role, "student")


class AdminUserManagementTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.auth_as(self.admin)

    def test_list_users_never_exposes_password(self):
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        for item in response.data:
            self.assertNotIn("password", item)

    def test_create_student_with_hashed_password(self):
        response = self.client.post(
            "/api/users/",
            {
                "username": "student2",
                "password": PASSWORD,
                "first_name": "Ali",
                "last_name": "Valiyev",
                "role": "student",
                "group": self.group.id,
            },
            format="json",
        )
        self.assertTrue(response.data["is_active"])
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertNotIn("password", response.data)
        user = User.objects.get(username="student2")
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(self.login("student2").status_code, status.HTTP_200_OK)

    def test_create_requires_password(self):
        response = self.client.post("/api/users/", {"username": "nopass", "role": "student"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_create_rejects_weak_password(self):
        response = self.client.post(
            "/api/users/", {"username": "weak", "password": "123", "role": "student"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_admin_role_cannot_be_given_on_create(self):
        response = self.client.post(
            "/api/users/", {"username": "admin2", "password": PASSWORD, "role": "admin"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)
        self.assertFalse(User.objects.filter(username="admin2").exists())

    def test_admin_role_cannot_be_given_on_update(self):
        for user in (self.teacher, self.student):
            response = self.client.patch(f"/api/users/{user.pk}/", {"role": "admin"}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, user.username)
            user.refresh_from_db()
            self.assertNotEqual(user.role, "admin")

    def test_teacher_and_student_roles_can_be_given(self):
        for role in ("teacher", "student"):
            response = self.client.post(
                "/api/users/", {"username": f"new_{role}", "password": PASSWORD, "role": role}, format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
            self.assertEqual(response.data["role"], role)

    def test_existing_admin_can_still_be_edited(self):
        response = self.client.patch(
            f"/api/users/{self.admin.pk}/", {"first_name": "Bosh", "role": "admin"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["role"], "admin")

    def test_group_only_for_students(self):
        response = self.client.post(
            "/api/users/",
            {"username": "teacher2", "password": PASSWORD, "role": "teacher", "group": self.group.id},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("group", response.data)

    def test_role_change_clears_group(self):
        response = self.client.patch(f"/api/users/{self.student.pk}/", {"role": "teacher"})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.student.refresh_from_db()
        self.assertIsNone(self.student.group)

    def test_teacher_role_change_clears_teaching_groups(self):
        response = self.client.patch(f"/api/users/{self.teacher.pk}/", {"role": "student"})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(self.group.teachers.count(), 0)

    def test_block_user(self):
        response = self.client.patch(f"/api/users/{self.student.pk}/", {"is_active": False})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials()
        self.assertEqual(self.login("student1").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_resets_password(self):
        response = self.client.patch(
            f"/api/users/{self.student.pk}/", {"password": "Yangi-Parol-2026"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.client.credentials()
        self.assertEqual(self.login("student1", "Yangi-Parol-2026").status_code, status.HTTP_200_OK)

    def test_admin_cannot_block_demote_or_delete_self(self):
        url = f"/api/users/{self.admin.pk}/"
        self.assertEqual(
            self.client.patch(url, {"is_active": False}).status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertEqual(
            self.client.patch(url, {"role": "student"}).status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.filter(pk=self.admin.pk, is_active=True, role="admin").exists())

    def test_delete_user(self):
        response = self.client.delete(f"/api/users/{self.student.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=self.student.pk).exists())


class AdminGroupManagementTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.auth_as(self.admin)

    def test_create_group_with_teacher(self):
        response = self.client.post(
            "/api/groups/", {"name": "DB-102", "teachers": [self.teacher.pk]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["teachers"], [self.teacher.pk])
        self.assertEqual(response.data["student_count"], 0)

    def test_duplicate_group_name_rejected(self):
        response = self.client.post("/api/groups/", {"name": "DB-101"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_only_teachers_can_be_assigned(self):
        response = self.client.post(
            "/api/groups/", {"name": "DB-103", "teachers": [self.student.pk]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("teachers", response.data)

    def test_list_shows_student_count(self):
        response = self.client.get("/api/groups/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["student_count"], 1)

    def test_delete_group_keeps_students(self):
        response = self.client.delete(f"/api/groups/{self.group.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.student.refresh_from_db()
        self.assertIsNone(self.student.group)


class SuperuserTests(APITestCase):
    def test_createsuperuser_gets_admin_role(self):
        user = User.objects.create_superuser("root", password=PASSWORD)
        self.assertEqual(user.role, User.Role.ADMIN)
