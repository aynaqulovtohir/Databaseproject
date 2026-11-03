"""Foydalanish sinovi hisoboti (labs/usability.py, docs/foydalanish-sinovi.md).

Ishga tushirish:
    python manage.py usability_report --group <guruh> --learn-lab <id> --exam-lab <id> [--sus <id>] [--names]

Jadvalda talabalar taxallus bilan (FS-01, FS-02, …); --names — ism-familiya bilan (faqat o'qituvchi uchun).
Loglardan faqat 2 (bajarildi) yoki 0 (bajarilmadi) olinadi; "yordam bilan" (1) kuzatuv varag'idan qo'shiladi.
"""
from django.core.management.base import BaseCommand, CommandError

from quizzes.models import Quiz
from quizzes.sus import is_sus
from users.models import StudentGroup, User

from ...models import Lab
from ...usability import TASKS, report


def _pct(done, n):
    return f"{done}/{n} ({round(100 * done / n)}%)" if n else "—"


class Command(BaseCommand):
    help = "Foydalanish sinovi: T1–T7 bajarilishi, log to'liqligi, AI ishlatilishi"

    def add_arguments(self, parser):
        parser.add_argument("--group", required=True, help="Sinov guruhi nomi")
        parser.add_argument("--learn-lab", type=int, required=True, help="O'quv ER laboratoriyasi id (T2–T5)")
        parser.add_argument("--exam-lab", type=int, required=True, help="Imtihon rejimidagi ER topshirig'i id (T6)")
        parser.add_argument("--sus", type=int, help="SUS so'rovnomasi id (T7)")
        parser.add_argument("--names", action="store_true", help="Taxallus o'rniga ism-familiya")

    def handle(self, *args, **options):
        group = StudentGroup.objects.filter(name=options["group"]).first()
        if group is None:
            raise CommandError(f"Bunday guruh yo'q: {options['group']}")
        labs = {}
        for key in ("learn_lab", "exam_lab"):
            labs[key] = Lab.objects.filter(pk=options[key], kind=Lab.Kind.ER).first()
            if labs[key] is None:
                raise CommandError(f"ER laboratoriyasi topilmadi: {options[key]}")
        sus = None
        if options["sus"]:
            sus = Quiz.objects.filter(pk=options["sus"]).first()
            if sus is None or not is_sus(sus):
                raise CommandError("SUS so'rovnomasi topilmadi.")
        students = User.objects.filter(role=User.Role.STUDENT, group=group, is_active=True).order_by("username")
        data = report(students, labs["learn_lab"], labs["exam_lab"], sus)

        out = self.stdout.write
        out(f"Guruh: {group.name}, talabalar: {data['students']}")
        out(f"{'Talaba':24} " + " ".join(TASKS) + "  holatlar(o'quv/imt)  maslahat+savol  baho  daq.")
        for index, row in enumerate(data["rows"], start=1):
            student = row["student"]
            name = f"{student.first_name} {student.last_name}".strip() or student.username if options["names"] else f"FS-{index:02d}"
            marks = " ".join(" -" if row["tasks"][t] is None else f"{row['tasks'][t]:>2}" for t in TASKS)
            out(f"{name[:24]:24} {marks}  {row['snapshots'][0]:>8}/{row['snapshots'][1]:<10} "
                f"{row['hints']}+{row['coach_questions']:<12} {row['grade_source'] or '-':5} {row['learn_minutes'] if row['learn_minutes'] is not None else '-'}")
        out("\nMustaqil bajarganlar (loglar bo'yicha):")
        for task in TASKS:
            item = data["tasks"][task]
            out(f"  {task}: {_pct(item['done'], item['n'])}")
        logs = data["logs"]
        out(f"\nLog to'liqligi ({logs['works']} ta ER ishi):")
        out(f"  (a) kamida {logs['min_snapshots']} oraliq holat: {_pct(logs['enough_snapshots'], logs['works'])}")
        out(f"  (b) jarayon topshirilgan diagrammagacha tiklanadi: {_pct(logs['reconstructed'], logs['works'])}")
        ai = data["ai"]
        out(f"\nAI: {ai['users']}/{data['students']} talaba foydalandi; maslahatlar {ai['hints']}, murabbiyga savollar {ai['coach_questions']}")
        out(f"O'quv laboratoriyasi baho manbasi: {data['grade_sources'] or '—'}")
        out("\nEslatma: 'yordam bilan' (1) va vaqt kuzatuv varag'idan qo'shiladi.")
