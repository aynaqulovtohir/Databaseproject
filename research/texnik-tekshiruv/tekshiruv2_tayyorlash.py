"""2-texnik tekshiruv: guruhlar, 20 ta sintetik hisob, testlar, imtihon modulidagi ER topshiriqlari.

Faqat MAHALLIY ishlab chiqish nusxasida ishlating (real serverda emas). Backend konteynerida:
    MUALLIF=<o'qituvchi logini> python manage.py shell < tekshiruv2_tayyorlash.py > tekshiruv2.json

Natija (stdout, oxirgi qator — JSON): hisoblar, laboratoriya va test id'lari, javoblar kaliti va namunaviy diagrammalar.
To'rt guruh (har bir shartda ikkita), hammasi «tadqiqotga kiradi»; test variantlari guruhlar bo'yicha almashlab beriladi.
"""
import json
import os
import secrets
from datetime import timedelta

from django.core.management import call_command
from django.utils import timezone

from labs.models import Lab, LabModule
from quizzes.models import Question, Quiz
from users.models import StudentGroup, User

teacher = User.objects.get(username=os.environ.get("MUALLIF", "sinov_oqituvchi"))
assert not StudentGroup.objects.filter(name__startswith="SIM2-").exists(), "SIM2 guruhlari allaqachon bor"


def source(title):
    lab = Lab.objects.filter(kind=Lab.Kind.ER, title__startswith=title, module__isnull=True).order_by("pk").first()
    assert lab is not None, f"Laboratoriya topilmadi: {title} (avval seed_design_labs)"
    return lab


def copy_lab(title, new_title, groups, module=None):
    lab = source(title)
    lab.pk = lab.id = None
    lab.title, lab.module, lab.author = new_title, module, teacher
    lab.save()
    lab.groups.set(groups)
    return lab


spec = [("SIM2-Tajriba-A", True, "A", "ta"), ("SIM2-Tajriba-B", True, "B", "tb"),
        ("SIM2-Nazorat-A", False, "A", "na"), ("SIM2-Nazorat-B", False, "B", "nb")]
groups, creds = {}, []
for name, ai, form, code in spec:
    g = StudentGroup.objects.create(name=name, ai_enabled=ai, in_study=True)
    g.teachers.add(teacher)
    groups[name] = g
    for i in range(1, 6):
        username, password = f"sim2_{code}{i}", secrets.token_urlsafe(9)
        User.objects.create_user(username=username, password=password, role=User.Role.STUDENT, group=g,
                                 first_name="SIM2", last_name=f"{name[5:]} {i}")
        creds.append((username, password, name, form))
for form in ("A", "B"):
    args = [f"--group={n}" for n, _, f, _ in spec if f == form]
    call_command("seed_entry_test", "--author", teacher.username, *args, "--kind", "both", "--form", form, verbosity=0)
    call_command("seed_entry_test", "--author", teacher.username, *args, "--kind", "delayed", "--form", form, verbosity=0)
call_command("seed_survey", "--author", teacher.username, *[f"--group={n}" for n in groups], verbosity=0)

now = timezone.now()
module = LabModule.objects.create(title="SIM2: o'lchov topshiriqlari (imtihon rejimi)", sequential=False, author=teacher,
                                  exam_starts_at=now - timedelta(minutes=1), exam_ends_at=now + timedelta(hours=3))
all_groups = list(groups.values())
labs = {
    "kirish": copy_lab("ER-model 1. Universitet", "SIM2 kirish ER: Universitet", all_groups, module).pk,
    "chiqish": copy_lab("ER-model 2. Kutubxona", "SIM2 chiqish ER: Kutubxona", all_groups, module).pk,
    "kechiktirilgan": copy_lab("ER-model 3. Shifoxona", "SIM2 kechiktirilgan ER: Shifoxona", all_groups, module).pk,
}
# AI funksiyalari nazorat guruhida bloklanishini tekshirish uchun imtihonsiz o'quv laboratoriyasi
learn = copy_lab("ER-model 2. Kutubxona", "SIM2 o'quv ER (imtihonsiz): Kutubxona", all_groups).pk

quizzes = {f"{q.kind}-{q.form}": q.pk for q in Quiz.objects.filter(groups__name__startswith="SIM2-").exclude(kind=Quiz.Kind.SURVEY).distinct()}
keys = {q.pk: [c.pk for c in q.choices.all() if c.is_correct] for q in Question.objects.filter(quiz_id__in=quizzes.values())}
refs = {pk: Lab.objects.get(pk=pk).reference_diagram for pk in [*labs.values(), learn]}
print(json.dumps({"creds": creds, "labs": labs, "learn": learn, "quizzes": quizzes, "keys": keys, "refs": refs},
                 ensure_ascii=False))
