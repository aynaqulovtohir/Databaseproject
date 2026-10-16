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


def future(days):
    return (timezone.now() + timedelta(days=days)).isoformat()


RUBRIC = [
    {"name": "ER-model", "points": 30, "description": "Obyektlar va bog'lanishlar", "stage": 0},
    {"name": "Jadvallar", "points": 40, "description": "Kalitlar va cheklovlar", "stage": 1},
    {"name": "Normallashtirish", "points": 30, "description": "", "stage": 1},
]
STAGES = [
    {"title": "ER-model", "description": "Konseptual model", "deadline": None},
    {"title": "Jadvallar", "description": "CREATE TABLE", "deadline": None},
]


class ProjectStagesTests(BaseTestCase):
    """Bosqichli loyiha va rubrika: yaratish, topshirish, mezonlar bo'yicha baholash, talabaga ko'rinishi."""

    def auth_as(self, user):
        # Login cheklovi (daqiqasiga 5) bu testlarda ko'p almashinuvga xalaqit bermasin
        self.client.force_authenticate(user)

    def create_project(self, rubric=RUBRIC, stages=STAGES):
        self.auth_as(self.teacher)
        stages = [{**stage, "deadline": future(3 + index * 7)} for index, stage in enumerate(stages)]
        return self.client.post(
            "/api/assignments/",
            {
                "title": "Yakuniy loyiha",
                "description": "Do'kon bazasi",
                "grading_criteria": "MAXFIY-MEZON",
                "groups": [self.group.pk],
                "rubric": rubric,
                "stages": stages,
            },
            format="json",
        )

    def make_project(self):
        response = self.create_project()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        project = Assignment.objects.get(pk=response.data["id"])
        return project, list(project.stages.all())

    def submit(self, project, stage, code=SQL):
        self.auth_as(self.student)
        return self.client.post(
            f"/api/assignments/{project.pk}/submissions/", {"sql_code": code, "stage": stage and stage.pk}, format="json"
        )

    def test_create_validates_rubric_and_stages(self):
        bad = [
            ([{**RUBRIC[0], "points": 50}, *RUBRIC[1:]], "yig'indisi"),
            ([{**item, "stage": 0} for item in RUBRIC], "2-bosqich"),
            ([{**RUBRIC[0], "stage": 5}, *RUBRIC[1:]], "bosqichni"),
            ([{**RUBRIC[0], "name": ""}, *RUBRIC[1:]], "nomi"),
            ([], "rubrika kerak"),
        ]
        for rubric, message in bad:
            response = self.create_project(rubric=rubric)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, rubric)
            self.assertIn(message, str(response.data["rubric"]), rubric)
        # Muddatlar tartibi
        self.auth_as(self.teacher)
        response = self.client.post(
            "/api/assignments/",
            {
                "title": "X", "description": "Y", "groups": [self.group.pk], "rubric": RUBRIC,
                "stages": [{**STAGES[0], "deadline": future(10)}, {**STAGES[1], "deadline": future(5)}],
            },
            format="json",
        )
        self.assertIn("stages", response.data)

    def test_project_deadline_is_last_stage_and_student_sees_rubric(self):
        project, stages = self.make_project()
        self.assertEqual(project.deadline, stages[-1].deadline)
        self.assertEqual(project.rubric[1], {**RUBRIC[1]})
        self.auth_as(self.student)
        data = self.client.get(f"/api/assignments/{project.pk}/").data
        self.assertEqual([stage["title"] for stage in data["stages"]], ["ER-model", "Jadvallar"])
        self.assertEqual(len(data["rubric"]), 3)
        self.assertNotIn("grading_criteria", data)
        self.assertNotIn("MAXFIY-MEZON", str(data))

    def test_stage_rules_on_submit(self):
        project, (first, second) = self.make_project()
        self.assertIn("stage", self.submit(project, None).data)
        self.assertIn("oldingi bosqich", str(self.submit(project, second).data))
        response = self.submit(project, first)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["stage"], first.pk)
        self.assertEqual(self.submit(project, second).status_code, status.HTTP_201_CREATED)
        # Boshqa topshiriqning bosqichi
        self.assertIn("stage", self.submit(self.assignment, first).data)
        # Urinishlar bosqich bo'yicha alohida raqamlanadi
        self.submit(project, first)
        numbers = Submission.objects.filter(assignment=project).values_list("stage__order", "attempt_number")
        self.assertEqual(sorted(numbers), [(0, 1), (0, 2), (1, 1)])

    def test_rubric_grading_per_stage(self):
        project, (first, second) = self.make_project()
        first_id = self.submit(project, first).data["id"]
        second_id = self.submit(project, second).data["id"]
        AIAnalysis.objects.filter(submission_id=second_id).update(status=AIAnalysis.Status.DONE, suggested_score=50)
        self.auth_as(self.teacher)
        url = lambda pk: f"/api/submissions/{pk}/grade/"
        # Mezonlar soni va chegaralari
        self.assertIn("rubric_scores", self.client.put(url(second_id), {"score": 60}, format="json").data)
        self.assertIn("rubric_scores", self.client.put(url(second_id), {"rubric_scores": [41, 30]}, format="json").data)
        self.assertIn("rubric_scores", self.client.put(url(second_id), {"rubric_scores": [10]}, format="json").data)
        response = self.client.put(url(second_id), {"rubric_scores": [35, 20], "comment": "Yaxshi"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        grade = Grade.objects.get(submission_id=second_id)
        self.assertEqual((grade.score, grade.max_score), (55, 70))
        self.assertEqual([item["name"] for item in grade.rubric_scores], ["Jadvallar", "Normallashtirish"])
        # AI 0–100 shkalada 50 deb baholagan: bosqichning 70 balidan 35
        self.assertEqual(grade.ai_suggested_score, 35)
        self.client.put(url(first_id), {"rubric_scores": [25]}, format="json")

        self.auth_as(self.student)
        data = self.client.get(f"/api/assignments/{project.pk}/").data["my_stages"]
        self.assertEqual(data["total_score"], 80)
        self.assertEqual([(item["score"], item["max_score"]) for item in data["items"]], [(25, 30), (55, 70)])
        mine = self.client.get(f"/api/submissions/{second_id}/").data["grade"]
        self.assertEqual(mine["rubric_scores"][0], {"name": "Jadvallar", "points": 40, "score": 35})
        self.assertNotIn("ai_suggested_score", mine)

    def test_graded_stage_blocks_resubmit_but_other_stage_open(self):
        project, (first, second) = self.make_project()
        first_id = self.submit(project, first).data["id"]
        self.auth_as(self.teacher)
        self.client.put(f"/api/submissions/{first_id}/grade/", {"rubric_scores": [30]}, format="json")
        self.assertIn("baholangan", str(self.submit(project, first).data))
        self.assertEqual(self.submit(project, second).status_code, status.HTTP_201_CREATED)

    def test_staff_list_shows_latest_per_stage(self):
        project, (first, second) = self.make_project()
        self.submit(project, first)
        self.submit(project, first)
        self.submit(project, second)
        self.auth_as(self.teacher)
        data = self.client.get(f"/api/assignments/{project.pk}/submissions/").data
        self.assertEqual(sorted((item["stage"], item["attempt_number"]) for item in data), [(first.pk, 2), (second.pk, 1)])

    def test_structure_locked_after_submissions(self):
        project, (first, _) = self.make_project()
        self.submit(project, first)
        self.auth_as(self.teacher)
        url = f"/api/assignments/{project.pk}/"
        changed_points = [{**RUBRIC[0], "points": 20}, {**RUBRIC[1], "points": 50}, RUBRIC[2]]
        self.assertIn("rubric", self.client.patch(url, {"rubric": changed_points}, format="json").data)
        self.assertIn("stages", self.client.patch(url, {"stages": [{**STAGES[0], "deadline": future(3)}]}, format="json").data)
        # Nomi va izohini, bosqich matni va muddatini o'zgartirish mumkin
        renamed = [{**RUBRIC[0], "name": "Konseptual model"}, *RUBRIC[1:]]
        new_stages = [{**STAGES[0], "title": "Model", "deadline": future(4)}, {**STAGES[1], "deadline": future(12)}]
        response = self.client.patch(url, {"rubric": renamed, "stages": new_stages}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        first.refresh_from_db()
        self.assertEqual(first.title, "Model")
        self.assertTrue(Submission.objects.filter(stage=first).exists())

    def test_simple_rubric_without_stages(self):
        self.auth_as(self.teacher)
        rubric = [{"name": "To'g'rilik", "points": 60}, {"name": "Uslub", "points": 40}]
        Assignment.objects.filter(pk=self.assignment.pk).update(rubric=[{**item, "description": "", "stage": None} for item in rubric])
        response = self.client.put(self.grade_url, {"rubric_scores": [50, 30]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["grade"]["score"], 80)
        self.assertEqual(response.data["grade"]["max_score"], 100)

    def test_ai_prompt_has_stage_and_its_rubric_only(self):
        from ai.services import build_analysis_messages

        project, (first, second) = self.make_project()
        self.submit(project, first)
        submission = Submission.objects.get(pk=self.submit(project, second).data["id"])
        text = build_analysis_messages(submission)[0]["content"]
        self.assertIn("2-bosqichi", text)
        self.assertIn("Normallashtirish (30 ball)", text)
        self.assertNotIn("ER-model (30 ball)", text)
        self.assertNotIn(self.student.username, text)


ER_DIAGRAM = {
    "entities": [
        {"id": "m", "name": "Mijoz", "x": 0, "y": 0, "attributes": [{"name": "id", "key": "pk"}, {"name": "ism", "key": ""}]},
        {"id": "b", "name": "Buyurtma", "x": 300, "y": 0, "attributes": [{"name": "id", "key": "pk"}]},
    ],
    "relationships": [{"id": "r", "name": "beradi", "source": "m", "target": "b", "source_card": "1", "target_card": "N"}],
}


class ErStageTests(ProjectStagesTests):
    """Bosqich turi «ER-diagramma»: talaba diagramma chizib topshiradi."""

    def make_project(self):
        response = self.create_project(stages=[{**STAGES[0], "kind": "er"}, STAGES[1]])
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        project = Assignment.objects.get(pk=response.data["id"])
        return project, list(project.stages.all())

    def submit(self, project, stage, code=SQL, diagram=None):
        self.auth_as(self.student)
        if diagram is None and stage is not None and stage.kind == "er":
            diagram = ER_DIAGRAM
        return self.client.post(
            f"/api/assignments/{project.pk}/submissions/",
            {"sql_code": code, "stage": stage and stage.pk, "diagram": diagram},
            format="json",
        )

    def test_er_stage_requires_valid_diagram(self):
        project, (first, second) = self.make_project()
        self.assertEqual(first.kind, "er")
        self.auth_as(self.student)
        url = f"/api/assignments/{project.pk}/submissions/"
        self.assertIn("diagram", self.client.post(url, {"stage": first.pk, "sql_code": SQL}, format="json").data)
        empty = {"entities": [], "relationships": []}
        self.assertIn("diagram", self.client.post(url, {"stage": first.pk, "diagram": empty}, format="json").data)
        broken = {"entities": [{"id": "a", "name": "", "x": 0, "y": 0, "attributes": []}], "relationships": []}
        self.assertIn("diagram", self.client.post(url, {"stage": first.pk, "diagram": broken}, format="json").data)
        response = self.client.post(url, {"stage": first.pk, "diagram": ER_DIAGRAM, "sql_code": "DROP TABLE x"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["sql_code"], "")
        self.assertEqual(response.data["diagram"]["entities"][0]["name"], "Mijoz")
        # SQL bosqichida SQL kerak
        self.assertIn("sql_code", self.client.post(url, {"stage": second.pk, "diagram": ER_DIAGRAM}, format="json").data)

    def test_ai_gets_diagram_as_text(self):
        from ai.services import build_analysis_messages

        project, (first, _) = self.make_project()
        submission = Submission.objects.get(pk=self.submit(project, first).data["id"])
        text = build_analysis_messages(submission)[0]["content"]
        self.assertIn("ER-diagramma", text)
        self.assertIn("Mijoz (1) — beradi — Buyurtma (N)", text)

    def test_kind_locked_after_submissions(self):
        project, (first, _) = self.make_project()
        self.submit(project, first)
        self.auth_as(self.teacher)
        stages = [{**STAGES[0], "kind": "sql", "deadline": future(3)}, {**STAGES[1], "deadline": future(12)}]
        response = self.client.patch(f"/api/assignments/{project.pk}/", {"stages": stages}, format="json")
        self.assertIn("turini", str(response.data["stages"]))
