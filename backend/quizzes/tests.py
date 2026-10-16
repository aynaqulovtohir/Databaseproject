"""Testlar moduli: ruxsatlar, javoblar yashirinligi, vaqt chegarasi va ball hisoblash."""
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import StudentGroup, User

from .models import Quiz, QuizAttempt
from .services import score_question

PASSWORD = "Sinov-parol-123"

QUESTIONS = [
    {
        "text": "Asosiy kalit nima uchun kerak?",
        "kind": "single",
        "points": 2,
        "choices": [
            {"text": "Har bir qatorni yagona aniqlash uchun", "is_correct": True},
            {"text": "Jadvalni chiroyli qilish uchun", "is_correct": False},
            {"text": "Ma'lumotni shifrlash uchun", "is_correct": False},
        ],
    },
    {
        "text": "Qaysilari cheklov (constraint)?",
        "kind": "multiple",
        "points": 4,
        "choices": [
            {"text": "PRIMARY KEY", "is_correct": True},
            {"text": "UNIQUE", "is_correct": True},
            {"text": "SELECT", "is_correct": False},
            {"text": "CHECK", "is_correct": True},
        ],
    },
]


class QuizTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.group = StudentGroup.objects.create(name="Q-guruh")
        cls.other_group = StudentGroup.objects.create(name="Boshqa")
        cls.teacher = User.objects.create_user("q_teacher", password=PASSWORD, role=User.Role.TEACHER)
        cls.other_teacher = User.objects.create_user("q_teacher2", password=PASSWORD, role=User.Role.TEACHER)
        cls.student = User.objects.create_user(
            "q_student", password=PASSWORD, role=User.Role.STUDENT, group=cls.group, first_name="Maxfiyism"
        )
        cls.student2 = User.objects.create_user("q_student2", password=PASSWORD, role=User.Role.STUDENT, group=cls.group)
        cls.outsider = User.objects.create_user(
            "q_outsider", password=PASSWORD, role=User.Role.STUDENT, group=cls.other_group
        )
        cls.group.teachers.add(cls.teacher)
        cls.other_group.teachers.add(cls.other_teacher)

    def setUp(self):
        cache.clear()

    def auth_as(self, user):
        response = self.client.post("/api/auth/login/", {"username": user.username, "password": PASSWORD})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def create_quiz(self, **extra):
        self.auth_as(self.teacher)
        data = {"kind": "pre", "title": "Kirish testi", "groups": [self.group.pk], "questions": QUESTIONS, **extra}
        response = self.client.post("/api/quizzes/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.client.credentials()
        return Quiz.objects.get(pk=response.data["id"])

    def choice_ids(self, quiz):
        """{savol tartibi: {"to'g'ri": [...], "noto'g'ri": [...]}}"""
        result = []
        for question in quiz.questions.all():
            choices = list(question.choices.all())
            result.append(
                (
                    str(question.pk),
                    [choice.pk for choice in choices if choice.is_correct],
                    [choice.pk for choice in choices if not choice.is_correct],
                )
            )
        return result


class QuizManagementTests(QuizTestCase):
    def test_teacher_creates_quiz_with_questions(self):
        quiz = self.create_quiz()
        self.assertEqual(quiz.questions.count(), 2)
        self.assertEqual(quiz.questions.first().choices.count(), 3)

    def test_question_validation(self):
        self.auth_as(self.teacher)
        bad = [{**QUESTIONS[0], "choices": [{"text": "a", "is_correct": True}, {"text": "b", "is_correct": True}]}]
        response = self.client.post(
            "/api/quizzes/", {"title": "T", "groups": [self.group.pk], "questions": bad}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post("/api/quizzes/", {"title": "T", "groups": [self.group.pk]}, format="json")
        self.assertIn("questions", response.data)

    def test_teacher_cannot_use_foreign_group(self):
        self.auth_as(self.teacher)
        data = {"title": "T", "groups": [self.other_group.pk], "questions": QUESTIONS}
        self.assertEqual(self.client.post("/api/quizzes/", data, format="json").status_code, 400)

    def test_other_teacher_and_student_cannot_manage(self):
        quiz = self.create_quiz()
        self.auth_as(self.other_teacher)
        self.assertEqual(self.client.get(f"/api/quizzes/{quiz.pk}/").status_code, status.HTTP_404_NOT_FOUND)
        self.auth_as(self.student)
        self.assertEqual(self.client.patch(f"/api/quizzes/{quiz.pk}/", {"title": "x"}).status_code, 403)
        self.assertEqual(self.client.get(f"/api/quizzes/{quiz.pk}/results/").status_code, 403)

    def test_questions_locked_after_start(self):
        quiz = self.create_quiz()
        self.auth_as(self.student)
        self.client.post(f"/api/quizzes/{quiz.pk}/start/")
        self.auth_as(self.teacher)
        response = self.client.patch(f"/api/quizzes/{quiz.pk}/", {"questions": QUESTIONS[:1]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Sarlavhani o'zgartirish mumkin
        self.assertEqual(self.client.patch(f"/api/quizzes/{quiz.pk}/", {"title": "Yangi"}).status_code, 200)

    def test_submitted_quiz_cannot_be_deleted(self):
        quiz = self.create_quiz()
        self.auth_as(self.student)
        self.client.post(f"/api/quizzes/{quiz.pk}/start/")
        self.client.post(f"/api/quizzes/{quiz.pk}/submit/", {"answers": {}}, format="json")
        self.auth_as(self.teacher)
        self.assertEqual(self.client.delete(f"/api/quizzes/{quiz.pk}/").status_code, 400)


class QuizDuplicateTests(QuizTestCase):
    def test_post_test_becomes_delayed_test_with_same_questions(self):
        quiz = self.create_quiz(kind="post", title="Chiqish testi")
        self.auth_as(self.student)
        self.client.post(f"/api/quizzes/{quiz.pk}/start/")
        self.auth_as(self.teacher)
        response = self.client.post(f"/api/quizzes/{quiz.pk}/duplicate/", {"kind": "delayed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        copy = Quiz.objects.get(pk=response.data["id"])
        self.assertEqual(copy.kind, Quiz.Kind.DELAYED)
        self.assertEqual(copy.title, "Chiqish testi — kechiktirilgan test")
        self.assertEqual(copy.author, self.teacher)
        self.assertEqual(list(copy.groups.all()), [self.group])
        original = [(q.text, [(c.text, c.is_correct) for c in q.choices.all()]) for q in quiz.questions.all()]
        copied = [(q.text, [(c.text, c.is_correct) for c in q.choices.all()]) for q in copy.questions.all()]
        self.assertEqual(copied, original)
        self.assertFalse(copy.attempts.exists())  # topshirishlar ko'chirilmaydi
        self.assertEqual(quiz.questions.count(), 2)  # asl test o'zgarmaydi

    def test_duplicate_rules(self):
        quiz = self.create_quiz()
        self.auth_as(self.teacher)
        self.assertEqual(self.client.post(f"/api/quizzes/{quiz.pk}/duplicate/", {"kind": "survey"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(f"/api/quizzes/{quiz.pk}/duplicate/", {"kind": "x"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(f"/api/quizzes/{quiz.pk}/duplicate/").data["title"], "Kirish testi (nusxa)")
        self.auth_as(self.student)
        self.assertEqual(self.client.post(f"/api/quizzes/{quiz.pk}/duplicate/").status_code, 403)
        self.auth_as(self.other_teacher)
        self.assertEqual(self.client.post(f"/api/quizzes/{quiz.pk}/duplicate/").status_code, 404)


class QuizTakingTests(QuizTestCase):
    def test_answers_are_hidden_from_student(self):
        quiz = self.create_quiz()
        self.auth_as(self.student)
        detail = self.client.get(f"/api/quizzes/{quiz.pk}/").data
        self.assertNotIn("questions", detail)
        self.assertEqual(detail["my_attempt"]["status"], "not_started")
        taking = self.client.post(f"/api/quizzes/{quiz.pk}/start/").data
        self.assertNotIn("is_correct", str(taking))
        self.assertEqual(len(taking["questions"]), 2)

    def test_outsider_does_not_see_quiz(self):
        quiz = self.create_quiz()
        self.auth_as(self.outsider)
        self.assertEqual(self.client.post(f"/api/quizzes/{quiz.pk}/start/").status_code, 404)

    def test_full_flow_and_single_attempt(self):
        quiz = self.create_quiz()
        (q1, right1, wrong1), (q2, right2, wrong2) = self.choice_ids(quiz)
        self.auth_as(self.student)
        self.client.post(f"/api/quizzes/{quiz.pk}/start/")
        # Oraliq saqlash
        response = self.client.put(f"/api/quizzes/{quiz.pk}/answers/", {"answers": {q1: right1}}, format="json")
        self.assertEqual(response.status_code, 200)
        # Ikkinchi savolda: 2 ta to'g'ri + 1 ta noto'g'ri -> (2-1)/3 * 4 = 1.33
        answers = {q1: right1, q2: right2[:2] + wrong2}
        result = self.client.post(f"/api/quizzes/{quiz.pk}/submit/", {"answers": answers}, format="json").data
        self.assertEqual(result["score"], 3.33)
        self.assertEqual(result["max_score"], 6)
        self.assertIsNone(result["questions"])  # show_answers=False

        again = self.client.post(f"/api/quizzes/{quiz.pk}/start/")
        self.assertEqual(again.status_code, status.HTTP_409_CONFLICT)
        response = self.client.post(f"/api/quizzes/{quiz.pk}/submit/", {"answers": {q1: wrong1[:1]}}, format="json")
        self.assertEqual(response.data["score"], 3.33)  # topshirilgan natija o'zgarmaydi

    def test_show_answers(self):
        quiz = self.create_quiz(show_answers=True)
        self.auth_as(self.student)
        self.client.post(f"/api/quizzes/{quiz.pk}/start/")
        result = self.client.post(f"/api/quizzes/{quiz.pk}/submit/", {"answers": {}}, format="json").data
        self.assertEqual(len(result["questions"]), 2)
        self.assertIn("is_correct", result["questions"][0]["choices"][0])

    def test_invalid_answers_rejected(self):
        quiz = self.create_quiz()
        other = self.create_quiz(title="Boshqa")
        (q1, right1, wrong1), _ = self.choice_ids(quiz)
        (_, foreign_right, _), _ = self.choice_ids(other)
        self.auth_as(self.student)
        self.client.post(f"/api/quizzes/{quiz.pk}/start/")
        url = f"/api/quizzes/{quiz.pk}/answers/"
        for answers in ({q1: foreign_right}, {q1: right1 + wrong1}, {"999999": right1}, {q1: "a"}, [1, 2]):
            response = self.client.put(url, {"answers": answers}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, answers)

    def test_time_limit_is_enforced_by_server(self):
        quiz = self.create_quiz(time_limit_minutes=10)
        (q1, right1, _), _ = self.choice_ids(quiz)
        self.auth_as(self.student)
        taking = self.client.post(f"/api/quizzes/{quiz.pk}/start/").data
        self.assertIsNotNone(taking["deadline"])
        self.client.put(f"/api/quizzes/{quiz.pk}/answers/", {"answers": {q1: right1}}, format="json")

        later = timezone.now() + timedelta(minutes=11)
        with patch("django.utils.timezone.now", return_value=later):
            response = self.client.put(f"/api/quizzes/{quiz.pk}/answers/", {"answers": {}}, format="json")
            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
            # Saqlangan javob baholangan, kechikkan yangi javob qabul qilinmagan
            self.assertEqual(response.data["result"]["score"], 2)

    def test_closed_quiz_cannot_be_started(self):
        quiz = self.create_quiz(opens_at=(timezone.now() + timedelta(days=1)).isoformat())
        self.auth_as(self.student)
        self.assertFalse(self.client.get(f"/api/quizzes/{quiz.pk}/").data["is_open"])
        self.assertEqual(self.client.post(f"/api/quizzes/{quiz.pk}/start/").status_code, 400)

    def test_teacher_results(self):
        quiz = self.create_quiz()
        (q1, right1, _), _ = self.choice_ids(quiz)
        self.auth_as(self.student)
        self.client.post(f"/api/quizzes/{quiz.pk}/start/")
        self.client.post(f"/api/quizzes/{quiz.pk}/submit/", {"answers": {q1: right1}}, format="json")
        self.auth_as(self.teacher)
        rows = {row["id"]: row for row in self.client.get(f"/api/quizzes/{quiz.pk}/results/").data}
        self.assertEqual(rows[self.student.pk]["status"], "submitted")
        self.assertEqual(rows[self.student.pk]["percent"], 33.3)
        self.assertEqual(rows[self.student2.pk]["status"], "not_started")


class ScoringTests(QuizTestCase):
    def test_multiple_choice_partial_credit_never_negative(self):
        quiz = self.create_quiz()
        question = quiz.questions.get(kind="multiple")
        (_, _, _), (_, right, wrong) = self.choice_ids(quiz)
        self.assertEqual(score_question(question, right), 4)
        self.assertEqual(score_question(question, right + wrong), 2.67)  # (3-1)/3
        self.assertEqual(score_question(question, wrong), 0)
        self.assertEqual(QuizAttempt.objects.count(), 0)


class QuizExportTests(QuizTestCase):
    def test_quiz_results_in_research_export_with_same_pseudonym(self):
        import csv
        import io
        import zipfile

        from labs.research import pseudonym

        quiz = self.create_quiz()
        (q1, right1, _), _ = self.choice_ids(quiz)
        self.auth_as(self.student)
        self.client.post(f"/api/quizzes/{quiz.pk}/start/")
        self.client.post(f"/api/quizzes/{quiz.pk}/submit/", {"answers": {q1: right1}}, format="json")

        self.auth_as(self.teacher)
        response = self.client.get("/api/labs/research-export/")
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        read = lambda name: list(  # noqa: E731
            csv.DictReader(io.StringIO(archive.read(name).decode("utf-8-sig")), delimiter=";")
        )
        rows = {row["talaba"]: row for row in read("testlar.csv")}
        mine = rows[pseudonym(self.student.pk)]
        self.assertEqual((mine["test_turi"], mine["holat"], mine["ball"], mine["foiz"]), ("kirish", "topshirgan", "2.0", "33.3"))
        self.assertEqual(rows[pseudonym(self.student2.pk)]["holat"], "boshlamagan")
        answers = read("test_javoblari.csv")
        self.assertEqual([(row["savol_raqami"], row["togri"]) for row in answers], [("1", "1"), ("2", "0")])
        everything = "".join(archive.read(name).decode("utf-8-sig") for name in archive.namelist())
        self.assertNotIn("Maxfiyism", everything)
        self.assertNotIn("q_student", everything)

        # Boshqa o'qituvchi bu testni eksportda ko'rmaydi
        self.auth_as(self.other_teacher)
        archive = zipfile.ZipFile(io.BytesIO(self.client.get("/api/labs/research-export/").content))
        self.assertEqual(read("testlar.csv"), [])


class EntryTestCommandTests(QuizTestCase):
    def test_question_bank_is_valid_and_pre_post_are_identical(self):
        from io import StringIO

        from django.core.management import call_command

        from .question_bank import QUESTIONS

        call_command("seed_entry_test", author="q_teacher", group=["Q-guruh"], stdout=StringIO())
        call_command("seed_entry_test", author="q_teacher", group=["Q-guruh"], stdout=StringIO())  # takrorlanmaydi
        pre, post = Quiz.objects.get(kind="pre"), Quiz.objects.get(kind="post")
        self.assertEqual(Quiz.objects.count(), 2)
        self.assertEqual(pre.questions.count(), len(QUESTIONS))
        self.assertEqual(pre.time_limit_minutes, 30)
        self.assertFalse(pre.show_answers)
        signature = lambda quiz: [  # noqa: E731
            (q.text, q.kind, q.points, [(c.text, c.is_correct) for c in q.choices.all()]) for q in quiz.questions.all()
        ]
        self.assertEqual(signature(pre), signature(post))
        self.assertTrue(pre.groups.filter(pk=self.group.pk).exists())

    def test_markdown_has_answer_key(self):
        from io import StringIO

        from django.core.management import call_command

        output = StringIO()
        call_command("seed_entry_test", markdown=True, stdout=output)
        self.assertIn("## Javoblar kaliti", output.getvalue())
        self.assertEqual(Quiz.objects.count(), 0)


SURVEY_QUESTIONS = [
    {"text": "Laboratoriya foydali bo'ldi.", "kind": "likert"},
    # Yuborilgan variantlar, to'g'ri belgisi va ball e'tiborga olinmaydi
    {"text": "AI maslahati tushunarli edi.", "kind": "likert", "points": 50,
     "choices": [{"text": "x", "is_correct": True}, {"text": "y", "is_correct": False}]},
]


class SurveyTests(QuizTestCase):
    """So'rovnoma (Likert shkalasi): ball qo'yilmaydi, o'qituvchi faqat umumlashgan natijani ko'radi."""

    def auth_as(self, user):
        # Bu testlarda login ko'p: login cheklovi (throttle) xalaqit bermasin
        cache.clear()
        super().auth_as(user)

    def create_survey(self):
        return self.create_quiz(kind="survey", title="So'rovnoma", questions=SURVEY_QUESTIONS)

    def answer(self, user, quiz, values):
        """values: har bir savol uchun shkaladagi qiymat (1-5) yoki None."""
        self.auth_as(user)
        taking = self.client.post(f"/api/quizzes/{quiz.pk}/start/").data
        answers = {
            str(question["id"]): [question["choices"][value - 1]["id"]]
            for question, value in zip(taking["questions"], values)
            if value is not None
        }
        response = self.client.post(f"/api/quizzes/{quiz.pk}/submit/", {"answers": answers}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return taking, response.data

    def test_likert_questions_get_standard_scale_and_no_points(self):
        from .models import LIKERT_SCALE

        quiz = self.create_survey()
        for question in quiz.questions.all():
            self.assertEqual(question.points, 0)
            self.assertEqual([choice.text for choice in question.choices.all()], LIKERT_SCALE)
            self.assertFalse(question.choices.filter(is_correct=True).exists())

    def test_survey_and_test_questions_are_not_mixed(self):
        self.auth_as(self.teacher)
        mixed = {"kind": "survey", "title": "S", "groups": [self.group.pk], "questions": SURVEY_QUESTIONS + QUESTIONS[:1]}
        self.assertEqual(self.client.post("/api/quizzes/", mixed, format="json").status_code, 400)
        likert_in_test = {"kind": "pre", "title": "T", "groups": [self.group.pk], "questions": SURVEY_QUESTIONS}
        self.assertEqual(self.client.post("/api/quizzes/", likert_in_test, format="json").status_code, 400)
        # Bor testning turini savollarni o'zgartirmasdan so'rovnomaga almashtirib bo'lmaydi
        quiz = self.create_quiz()
        self.auth_as(self.teacher)
        self.assertEqual(self.client.patch(f"/api/quizzes/{quiz.pk}/", {"kind": "survey"}).status_code, 400)

    def test_scale_is_not_shuffled_and_single_answer_only(self):
        quiz = self.create_survey()
        self.auth_as(self.student)
        taking = self.client.post(f"/api/quizzes/{quiz.pk}/start/").data
        question = taking["questions"][0]
        self.assertEqual(question["choices"][0]["text"], "Mutlaqo qo'shilmayman")
        self.assertEqual(question["choices"][-1]["text"], "To'liq qo'shilaman")
        two = [question["choices"][0]["id"], question["choices"][1]["id"]]
        response = self.client.put(f"/api/quizzes/{quiz.pk}/answers/", {"answers": {str(question["id"]): two}}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Boshqa savolning varianti qabul qilinmaydi
        other = taking["questions"][1]["choices"][0]["id"]
        response = self.client.put(f"/api/quizzes/{quiz.pk}/answers/", {"answers": {str(question["id"]): [other]}}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_summary_by_group_without_individual_answers(self):
        quiz = self.create_survey()
        control = StudentGroup.objects.create(name="Nazorat", ai_enabled=False)
        control.teachers.add(self.teacher)
        quiz.groups.add(control)
        control_student = User.objects.create_user("q_control", password=PASSWORD, role=User.Role.STUDENT, group=control)
        self.group.ai_enabled = True
        self.group.save()

        _, result = self.answer(self.student, quiz, [5, 4])
        self.assertEqual((result["score"], result["max_score"]), (0, 0))
        self.auth_as(self.teacher)
        # Bitta javob: natija yashiriladi (aks holda talabaning javobi ochilib qoladi)
        first = self.client.get(f"/api/quizzes/{quiz.pk}/survey/").data["questions"][0]
        self.assertEqual(first["all"], {"count": 1, "mean": None, "distribution": None, "hidden": True})

        more = [
            User.objects.create_user(f"q_extra{index}", password=PASSWORD, role=User.Role.STUDENT, group=group)
            for index, group in enumerate([self.group, control, control])
        ]
        self.answer(self.student2, quiz, [3, None])
        self.answer(control_student, quiz, [1, 2])
        self.answer(more[1], quiz, [1, 2])

        # 4 ta javob (AI: 2, nazorat: 2): umumiy natija ko'rinadi, qismlar esa yashirin
        self.auth_as(self.teacher)
        first, second = self.client.get(f"/api/quizzes/{quiz.pk}/survey/").data["questions"]
        self.assertEqual(first["all"], {"count": 4, "mean": 2.5, "distribution": [2, 0, 1, 0, 1], "hidden": False})
        self.assertTrue(first["ai"]["hidden"] and first["control"]["hidden"])
        self.assertIsNone(first["ai"]["mean"])
        # 2-savolga 3 kishi javob bergan: AI qismida 1 ta — ikkala qism ham yashirin
        self.assertEqual(second["all"]["count"], 3)
        self.assertTrue(second["ai"]["hidden"] and second["control"]["hidden"])

        self.answer(more[0], quiz, [2, 4])
        self.answer(more[2], quiz, [3, 3])
        self.auth_as(self.teacher)
        summary = self.client.get(f"/api/quizzes/{quiz.pk}/survey/").data
        self.assertEqual(summary["respondents"], 6)
        first = summary["questions"][0]
        self.assertEqual(first["ai"], {"count": 3, "mean": 3.33, "distribution": [0, 1, 1, 0, 1], "hidden": False})
        self.assertEqual(first["control"]["mean"], 1.67)
        # Javoblar ism bilan bog'lanmaydi
        self.assertNotIn("Maxfiyism", str(summary))
        self.assertNotIn("q_student", str(summary))

    def test_summary_access(self):
        quiz = self.create_survey()
        self.auth_as(self.student)
        self.assertEqual(self.client.get(f"/api/quizzes/{quiz.pk}/survey/").status_code, 403)
        self.auth_as(self.other_teacher)
        self.assertEqual(self.client.get(f"/api/quizzes/{quiz.pk}/survey/").status_code, 404)
        regular = self.create_quiz()
        self.auth_as(self.teacher)
        self.assertEqual(self.client.get(f"/api/quizzes/{regular.pk}/survey/").status_code, 400)

    def test_survey_answers_in_export(self):
        import csv
        import io
        import zipfile

        quiz = self.create_survey()
        self.answer(self.student, quiz, [5, None])
        self.auth_as(self.teacher)
        archive = zipfile.ZipFile(io.BytesIO(self.client.get("/api/labs/research-export/").content))
        read = lambda name: list(  # noqa: E731
            csv.DictReader(io.StringIO(archive.read(name).decode("utf-8-sig")), delimiter=";")
        )
        quizzes = [row for row in read("testlar.csv") if row["holat"] == "topshirgan"]
        self.assertEqual([(row["test_turi"], row["ball"], row["foiz"]) for row in quizzes], [("sorovnoma", "", "")])
        answers = read("test_javoblari.csv")
        self.assertEqual([(row["savol_turi"], row["javob"], row["togri"]) for row in answers], [("likert", "5", ""), ("likert", "", "")])

    def test_seed_survey(self):
        from io import StringIO

        from django.core.management import call_command

        from .survey_bank import STATEMENTS

        control = StudentGroup.objects.create(name="Nazorat", ai_enabled=False)
        call_command("seed_survey", author="q_teacher", group=["Q-guruh", "Nazorat"], stdout=StringIO())
        call_command("seed_survey", author="q_teacher", group=["Q-guruh", "Nazorat"], stdout=StringIO())
        surveys = Quiz.objects.filter(kind="survey")
        self.assertEqual(surveys.count(), 2)
        full = surveys.get(groups=self.group)
        short = surveys.get(groups=control)
        self.assertEqual(full.questions.count(), len(STATEMENTS))
        self.assertEqual(short.questions.count(), sum(1 for item in STATEMENTS if not item["ai"]))
        self.assertFalse(short.questions.filter(text__icontains="AI").exists())
