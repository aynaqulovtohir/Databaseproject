"""Kirish va ruxsatlar testlari."""
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import IssuedRefreshToken, StudentGroup, User

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


class RefreshRevocationTests(BaseTestCase):
    """Refresh token almashtiriladi, bekor qilinadi va o'g'irlangan nusxa sessiyalarni yopadi (users/tokens.py)."""

    def refresh(self, cookie=None):
        if cookie is not None:
            self.client.cookies["refresh_token"] = cookie
        return self.client.post("/api/auth/refresh/")

    def cookie(self):
        return self.client.cookies["refresh_token"].value

    def age_tokens(self, user):
        # Token ikki daqiqa oldin almashtirilgandek: bir vaqtda ochilgan tablar oralig'idan ancha keyin
        IssuedRefreshToken.objects.filter(user=user, used_at__isnull=False).update(
            used_at=timezone.now() - timedelta(minutes=2)
        )

    def test_refresh_rotates_cookie_and_keeps_session_expiry(self):
        self.login("student1")
        first = self.cookie()
        response = self.refresh()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        second = response.cookies["refresh_token"].value
        self.assertNotEqual(second, first)
        self.assertTrue(response.cookies["refresh_token"]["httponly"])
        # Sessiya login vaqtidan hisoblanadi: yangilash uni uzaytirmaydi
        self.assertEqual(RefreshToken(second)["exp"], RefreshToken(first)["exp"])
        self.assertEqual(self.refresh().status_code, status.HTTP_200_OK)

    def test_reused_token_revokes_all_sessions(self):
        self.login("student1")
        stolen = self.cookie()
        self.assertEqual(self.refresh().status_code, status.HTTP_200_OK)
        current = self.cookie()
        self.age_tokens(self.student)
        # Hujumchi eski nusxani ishlatadi: rad etiladi va haqiqiy foydalanuvchining sessiyasi ham yopiladi
        response = self.refresh(stolen)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.cookies["refresh_token"].value, "")
        self.assertEqual(self.refresh(current).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(IssuedRefreshToken.objects.filter(user=self.student, revoked_at__isnull=True).exists())

    def test_reuse_by_attacker_first_is_detected(self):
        # Hujumchi birinchi bo'lib yangilaydi; foydalanuvchi eski cookie bilan kelganda ikkala sessiya yopiladi
        self.login("student1")
        stolen = self.cookie()
        attacker = APIClient()
        attacker.cookies["refresh_token"] = stolen
        attacker_response = attacker.post("/api/auth/refresh/")
        self.assertEqual(attacker_response.status_code, status.HTTP_200_OK)
        self.age_tokens(self.student)
        self.assertEqual(self.refresh(stolen).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(attacker.post("/api/auth/refresh/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_concurrent_tabs_within_grace_get_access_only(self):
        self.login("student1")
        old = self.cookie()
        self.assertEqual(self.refresh().status_code, status.HTTP_200_OK)
        current = self.cookie()
        # Ikkinchi tab xuddi shu paytda eski cookie bilan keldi
        other_tab = APIClient()
        other_tab.cookies["refresh_token"] = old
        response = other_tab.post("/api/auth/refresh/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh_token", response.cookies)
        # Sessiyalar yopilmadi
        self.assertEqual(self.refresh(current).status_code, status.HTTP_200_OK)

    def test_logout_revokes_token(self):
        self.login("student1")
        cookie = self.cookie()
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, status.HTTP_204_NO_CONTENT)
        # Cookie nusxasi saqlab qolingan bo'lsa ham ishlamaydi
        self.assertEqual(self.refresh(cookie).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_with_bad_cookie(self):
        self.client.cookies["refresh_token"] = "soxta-token"
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, status.HTTP_204_NO_CONTENT)

    def test_change_password_revokes_other_sessions_keeps_current(self):
        self.login("student1")
        other_device = self.cookie()
        self.auth_as(self.student)
        response = self.client.post(
            "/api/auth/change-password/", {"old_password": PASSWORD, "new_password": "Yangi-Parol-2026"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        current = response.cookies["refresh_token"].value
        self.assertEqual(self.refresh(other_device).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.refresh(current).status_code, status.HTTP_200_OK)

    def admin_change_revokes(self, change):
        student = APIClient()
        student.post("/api/auth/login/", {"username": "student1", "password": PASSWORD})
        self.auth_as(self.admin)
        response = self.client.patch(f"/api/users/{self.student.pk}/", change)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Blokdan chiqarilsa ham eski sessiya qaytmaydi
        User.objects.filter(pk=self.student.pk).update(is_active=True)
        self.assertEqual(student.post("/api/auth/refresh/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_password_reset_revokes_sessions(self):
        self.admin_change_revokes({"password": "Admin-Bergan-2026"})

    def test_admin_block_revokes_sessions(self):
        self.admin_change_revokes({"is_active": False})

    def test_unregistered_token_rejected(self):
        # Ro'yxatga olinmagan (masalan, bu o'zgarishdan oldin berilgan) token imzosi to'g'ri bo'lsa ham qabul qilinmaydi
        self.assertEqual(self.refresh(str(RefreshToken.for_user(self.student))).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_records_cleaned_on_login(self):
        self.login("student1")
        IssuedRefreshToken.objects.filter(user=self.student).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.login("student1")
        self.assertEqual(IssuedRefreshToken.objects.filter(user=self.student).count(), 1)
