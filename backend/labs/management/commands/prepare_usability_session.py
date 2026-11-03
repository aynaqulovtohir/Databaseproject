"""Foydalanish sinovi mashg'ulotini bitta buyruq bilan tayyorlash (docs/foydalanish-sinovi.md).

Ishga tushirish:
    python manage.py prepare_usability_session --author <o'qituvchi> --group FS-2026 --count 15 \
        --start "2026-11-20 10:00" [--prefix fs] [--learn-lab <id>] [--exam-lab <id>] [--cards kartochkalar.html]

Yaratadi:
- guruh (AI yoqilgan, «Tadqiqotga kiradi» belgilanmagan) va unga N ta talaba hisobi (tasodifiy parollar bilan);
- o'quv ER laboratoriyasi nusxasi (imtihonsiz, AI bilan; standart — «Kutubxona»);
- alohida modulda imtihon rejimidagi ER topshirig'i (standart — «Shifoxona»): mashg'ulot boshidan 45–70-daqiqalar;
- SUS so'rovnomasi (seed_sus);
- login kartochkalari (chop etishga tayyor HTML) va hisobot buyruqlari.

Parollar faqat kartochkalar faylida va ekranda bo'ladi: chop etgach faylni o'chiring.
"""
import html
import secrets
from datetime import datetime, timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from quizzes.models import Quiz
from quizzes.sus_bank import SUS_TITLE
from users.models import StudentGroup, User

from ...models import Lab, LabModule

LEARN_TITLE = "ER-model 2. Kutubxona"
EXAM_TITLE = "ER-model 3. Shifoxona"
EXAM_START, EXAM_END = 45, 70  # daqiqa, mashg'ulot boshidan
# Chalkashtiriladigan belgilarsiz (0/O, 1/l/I)
ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_password(length=10):
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def source_lab(lab_id, title):
    if lab_id:
        lab = Lab.objects.filter(pk=lab_id, kind=Lab.Kind.ER).first()
    else:
        lab = Lab.objects.filter(kind=Lab.Kind.ER, title__startswith=title, module__isnull=True).order_by("pk").first()
    if lab is None:
        raise CommandError(f"ER laboratoriyasi topilmadi: {lab_id or title}. --learn-lab / --exam-lab bilan id bering.")
    return lab


def copy_lab(lab, title, author, group, module=None):
    """Manba laboratoriyaning nusxasi (manba o'zgarmaydi): faqat shu guruhga ko'rinadi."""
    lab.pk = lab.id = None
    lab.title, lab.author, lab.module = title, author, module
    lab.save()
    lab.groups.set([group])
    return lab


def cards_html(group, start, accounts, url):
    cards = "\n".join(
        f'<div class="card"><div class="head">«MB loyihalash» — foydalanish sinovi</div>'
        f'<div class="row"><span>Taxallus</span><b>FS-{index:02d}</b></div>'
        f'<div class="row"><span>Login</span><code>{html.escape(username)}</code></div>'
        f'<div class="row"><span>Parol</span><code>{html.escape(password)}</code></div>'
        f'<div class="url">{html.escape(url)}</div></div>'
        for index, (username, password) in enumerate(accounts, start=1)
    )
    return f"""<!doctype html><html lang="uz"><head><meta charset="utf-8">
<title>Login kartochkalari — {html.escape(group)}</title>
<style>
@page {{ size: A4; margin: 12mm; }}
body {{ font-family: Arial, sans-serif; margin: 0; color: #111; }}
h1 {{ font-size: 14pt; margin: 0 0 4mm; }}
p {{ font-size: 9pt; margin: 0 0 6mm; color: #444; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6mm; }}
.card {{ border: 1px dashed #777; padding: 5mm; break-inside: avoid; }}
.head {{ font-size: 9pt; color: #555; margin-bottom: 3mm; }}
.row {{ display: flex; justify-content: space-between; font-size: 12pt; margin: 1.5mm 0; }}
.row span {{ color: #555; }}
code {{ font-family: "Courier New", monospace; font-size: 14pt; letter-spacing: 1px; }}
.url {{ font-size: 9pt; color: #555; margin-top: 3mm; }}
</style></head><body>
<h1>Login kartochkalari — {html.escape(group)}, {start:%d.%m.%Y %H:%M}</h1>
<p>Qirqib, har bir talabaga bittadan bering. Taxallus kuzatuv varag'idagi qatorga mos keladi.
Chop etgach bu faylni o'chiring: unda parollar bor.</p>
<div class="grid">
{cards}
</div></body></html>
"""


class Command(BaseCommand):
    help = "Foydalanish sinovi uchun guruh, hisoblar, laboratoriyalar, SUS va login kartochkalarini tayyorlaydi"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True, help="O'qituvchi yoki admin logini")
        parser.add_argument("--group", required=True, help="Yangi guruh nomi, masalan FS-2026")
        parser.add_argument("--count", type=int, default=15, help="Talabalar soni (standart 15)")
        parser.add_argument("--start", required=True, help='Mashg\'ulot boshlanishi: "YYYY-MM-DD HH:MM" (Toshkent vaqti)')
        parser.add_argument("--prefix", default="fs", help="Login prefiksi (standart fs → fs01, fs02, …)")
        parser.add_argument("--learn-lab", type=int, help="O'quv ER laboratoriyasi manbasi id (standart «Kutubxona»)")
        parser.add_argument("--exam-lab", type=int, help="Imtihon ER topshirig'i manbasi id (standart «Shifoxona»)")
        parser.add_argument("--cards", default="kartochkalar.html", help="Login kartochkalari fayli")
        parser.add_argument("--url", default="", help="Kartochkada ko'rsatiladigan sayt manzili")

    def handle(self, *args, **options):
        try:
            author = User.objects.get(username=options["author"])
        except User.DoesNotExist:
            raise CommandError(f"Bunday foydalanuvchi yo'q: {options['author']}")
        if author.is_student:
            raise CommandError("Muallif talaba bo'la olmaydi.")
        if not 1 <= options["count"] <= 60:
            raise CommandError("--count 1 dan 60 gacha bo'lsin.")
        try:
            start = timezone.make_aware(datetime.strptime(options["start"], "%Y-%m-%d %H:%M"))
        except ValueError:
            raise CommandError('--start "YYYY-MM-DD HH:MM" shaklida bo\'lsin, masalan "2026-11-20 10:00".')
        name = options["group"]
        if StudentGroup.objects.filter(name=name).exists():
            raise CommandError(f"«{name}» guruhi allaqachon bor. Boshqa nom bering.")
        prefix = options["prefix"]
        usernames = [f"{prefix}{index:02d}" for index in range(1, options["count"] + 1)]
        taken = sorted(User.objects.filter(username__in=usernames).values_list("username", flat=True))
        if taken:
            raise CommandError(f"Bu loginlar band: {', '.join(taken)}. Boshqa --prefix bering.")
        learn_src = source_lab(options["learn_lab"], LEARN_TITLE)
        exam_src = source_lab(options["exam_lab"], EXAM_TITLE)
        if learn_src.pk == exam_src.pk:
            raise CommandError("O'quv laboratoriyasi va imtihon topshirig'i turli bo'lishi kerak.")

        with transaction.atomic():
            group = StudentGroup.objects.create(name=name, ai_enabled=True, in_study=False)
            if author.is_teacher:
                group.teachers.add(author)
            accounts = []
            for username in usernames:
                password = new_password()
                User.objects.create_user(username=username, password=password, role=User.Role.STUDENT, group=group)
                accounts.append((username, password))
            learn = copy_lab(learn_src, f"{name}: {learn_src.title}", author, group)
            module = LabModule.objects.create(
                title=f"{name}: AI'siz topshiriq (imtihon rejimi)", sequential=False, author=author,
                exam_starts_at=start + timedelta(minutes=EXAM_START), exam_ends_at=start + timedelta(minutes=EXAM_END),
            )
            exam = copy_lab(exam_src, f"{name}: {exam_src.title}", author, group, module)
            call_command("seed_sus", "--author", author.username, "--group", name, verbosity=0, stdout=self.stdout)
            sus = Quiz.objects.get(title=SUS_TITLE, author=author, kind=Quiz.Kind.SURVEY)

        local = timezone.localtime(start)
        with open(options["cards"], "w", encoding="utf-8") as handle:
            handle.write(cards_html(name, local, accounts, options["url"]))

        out = self.stdout.write
        out(self.style.SUCCESS(f"«{name}» tayyor: {len(accounts)} ta hisob."))
        out(f"O'quv laboratoriyasi: id {learn.pk} — {learn.title}")
        exam_from = timezone.localtime(module.exam_starts_at)
        exam_to = timezone.localtime(module.exam_ends_at)
        out(f"Imtihon topshirig'i: id {exam.pk} — {exam.title} ({exam_from:%d.%m %H:%M}–{exam_to:%H:%M})")
        out(f"SUS so'rovnomasi: id {sus.pk}")
        out(f"Login kartochkalari: {options['cards']} (chop etgach o'chiring)")
        out("\nMashg'ulotdan keyin:")
        out(f"  python manage.py usability_report --group {name} --learn-lab {learn.pk} --exam-lab {exam.pk} --sus {sus.pk}")
        out(f"  python manage.py sus_report --quiz {sus.pk} --group {name} --consented")
