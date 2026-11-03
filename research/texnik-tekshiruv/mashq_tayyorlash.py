"""Foydalanish sinovi MASHQI: AI yoqilgan, tadqiqotga belgilanmagan FS-MASHQ guruhi, o'zbekcha ismli 12 ta sintetik
hisob, o'quv laboratoriyasi («Kutubxona»), imtihon rejimidagi topshiriq («Shifoxona») va SUS so'rovnomasi.

Faqat MAHALLIY nusxada. Backend konteynerida:
    MUALLIF=<o'qituvchi logini> python manage.py shell < mashq_tayyorlash.py > mashq.json
"""
import json
import os
import secrets
from datetime import timedelta
from django.core.management import call_command
from django.utils import timezone
from users.models import User, StudentGroup
from labs.models import Lab, LabModule
from quizzes.models import Quiz
from quizzes.sus_bank import SUS_TITLE

teacher = User.objects.get(username=os.environ.get("MUALLIF", "sinov_oqituvchi"))
assert not StudentGroup.objects.filter(name="FS-MASHQ").exists()
g = StudentGroup.objects.create(name="FS-MASHQ", ai_enabled=True, in_study=False); g.teachers.add(teacher)
NAMES = [("Dilnoza", "Karimova"), ("Jasur", "Toshmatov"), ("Madina", "Yusupova"), ("Sardor", "Rahimov"),
         ("Nilufar", "Abdullayeva"), ("Bekzod", "Ergashev"), ("Shahnoza", "Mirzayeva"), ("Otabek", "Qodirov"),
         ("Zarina", "Nazarova"), ("Javohir", "Islomov"), ("Malika", "Sobirova"), ("Sherzod", "Usmonov")]
creds = []
for i, (first, last) in enumerate(NAMES, 1):
    username, password = f"fs_{i:02d}", secrets.token_urlsafe(9)
    User.objects.create_user(username=username, password=password, role=User.Role.STUDENT, group=g, first_name=first, last_name=last)
    creds.append((username, password, f"{first} {last}"))
learn = Lab.objects.filter(kind=Lab.Kind.ER, title__startswith="ER-model 2. Kutubxona", module__isnull=True).order_by("pk").first(); learn.pk = None; learn.id = None
learn.title = "Mashq: ER-model 2. Kutubxona"; learn.module = None; learn.author = teacher; learn.save(); learn.groups.set([g])
now = timezone.now()
module = LabModule.objects.create(title="Mashq: AI'siz topshiriq (imtihon rejimi)", sequential=False, order=97,
                                  exam_starts_at=now - timedelta(minutes=1), exam_ends_at=now + timedelta(hours=2), author=teacher)
exam = Lab.objects.filter(kind=Lab.Kind.ER, title__startswith="ER-model 3. Shifoxona", module__isnull=True).order_by("pk").first(); exam.pk = None; exam.id = None
exam.title = "Mashq imtihon: ER-model 3. Shifoxona"; exam.module = module; exam.author = teacher; exam.save(); exam.groups.set([g])
call_command("seed_sus", "--author", teacher.username, "--group", "FS-MASHQ", verbosity=0)
sus = Quiz.objects.get(title=SUS_TITLE, author=teacher)
print(json.dumps({"creds": creds, "learn": learn.pk, "exam": exam.pk, "sus": sus.pk, "learn_ref": learn.reference_diagram, "exam_ref": exam.reference_diagram,
                  "start": now.isoformat()}, ensure_ascii=False))
