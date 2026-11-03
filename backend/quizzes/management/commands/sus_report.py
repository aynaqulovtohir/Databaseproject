"""SUS so'rovnomasi natijasi: guruh bo'yicha o'rtacha, 95% CI, baho, Cronbach α va fikrlar bo'yicha o'rtachalar.

Ishga tushirish:
    python manage.py sus_report --quiz <id> [--group <guruh> ...] [--consented] [--json]

--consented — faqat tadqiqotga rozi bo'lgan talabalar (maqola uchun shu bilan hisoblang).
"""
import json

from django.core.management.base import BaseCommand, CommandError

from users.models import StudentGroup, User

from ...models import Quiz
from ...sus import BENCHMARK, is_sus, report


class Command(BaseCommand):
    help = "SUS so'rovnomasi natijasini hisoblaydi"

    def add_arguments(self, parser):
        parser.add_argument("--quiz", type=int, required=True, help="SUS so'rovnomasi id raqami")
        parser.add_argument("--group", action="append", default=[], help="Faqat shu guruh(lar) talabalari")
        parser.add_argument("--consented", action="store_true", help="Faqat tadqiqotga rozi bo'lgan talabalar")
        parser.add_argument("--json", action="store_true", help="Natijani JSON ko'rinishida chiqarish")

    def handle(self, *args, **options):
        quiz = Quiz.objects.filter(pk=options["quiz"]).first()
        if quiz is None or not is_sus(quiz):
            raise CommandError("Bu id bo'yicha SUS so'rovnomasi topilmadi (seed_sus bilan yaratilgan bo'lishi kerak).")
        students = User.objects.filter(role=User.Role.STUDENT)
        if options["group"]:
            groups = StudentGroup.objects.filter(name__in=options["group"])
            if groups.count() != len(set(options["group"])):
                raise CommandError("Ko'rsatilgan guruhlardan biri topilmadi.")
            students = students.filter(group__in=groups)
        if options["consented"]:
            from users.consent import research_participants

            students = research_participants(students)
        data = report(quiz, students)
        if options["json"]:
            data["scores"] = sorted(data["scores"].values())
            self.stdout.write(json.dumps(data, ensure_ascii=False, indent=2))
            return
        s = data["summary"]
        self.stdout.write(f"{quiz.title} (id {quiz.pk})")
        self.stdout.write(f"Topshirgan: {data['submitted']}, to'liqsiz (hisobga olinmadi): {data['incomplete']}, hisoblandi: {s['n']}")
        if not s["n"]:
            return
        self.stdout.write(f"SUS: M = {s['mean']}, SD = {s['sd']}, Mdn = {s['median']}, oraliq {s['min']}–{s['max']}")
        if s["ci95"]:
            self.stdout.write(f"95% CI: [{s['ci95'][0]}; {s['ci95'][1]}]")
        self.stdout.write(f"Baho (Sauro–Lewis): {s['grade']}; qabul qilinish (Bangor va boshq., 2008): {s['acceptability']}")
        if s["benchmark"]:
            b = s["benchmark"]
            self.stdout.write(f"{BENCHMARK:g} me'yoridan farq: t({b['df']}) = {b['t']}, p = {b['p']}")
        self.stdout.write(f"Cronbach α: {s['alpha']}")
        self.stdout.write("Fikrlar bo'yicha o'rtacha (1–5):")
        for item in data["items"]:
            sign = "+" if item["positive"] else "−"
            self.stdout.write(f"  {item['order']:>2} ({sign}) M = {item['mean']}, SD = {item['sd']}, n = {item['n']}: {item['text']}")
