"""Loyihalash bo'yicha tayyor laboratoriyalarni bazaga qo'shadi (design_labs.py).

Ishga tushirish:
    python manage.py seed_design_labs --author <o'qituvchi logini> --group <guruh nomi> [--group ...] [--update]

Qayta ishga tushirilsa, bor laboratoriyalar takrorlanmaydi; --update berilsa, ularning
sharti va SQL kodi yangilanadi. Har bir laboratoriya saqlashdan oldin qum qutida tekshiriladi.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from users.models import StudentGroup, User

from ...checker import LabSetupError, validate_lab_sql
from ...design_labs import DESIGN_LABS
from ...models import Lab


class Command(BaseCommand):
    help = "Loyihalash bo'yicha tayyor laboratoriyalarni qo'shadi"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True, help="Laboratoriyalar muallifi (o'qituvchi yoki admin logini)")
        parser.add_argument("--group", action="append", default=[], help="Biriktiriladigan guruh nomi")
        parser.add_argument("--update", action="store_true", help="Bor laboratoriyalarni ham yangilash")

    def handle(self, *args, **options):
        try:
            author = User.objects.get(username=options["author"])
        except User.DoesNotExist:
            raise CommandError(f"Bunday foydalanuvchi yo'q: {options['author']}")
        if author.is_student:
            raise CommandError("Laboratoriya muallifi talaba bo'la olmaydi.")

        groups = list(StudentGroup.objects.filter(name__in=options["group"]))
        missing = set(options["group"]) - {group.name for group in groups}
        if missing:
            raise CommandError(f"Bunday guruh yo'q: {', '.join(sorted(missing))}")

        for lab_data in DESIGN_LABS:
            try:
                validate_lab_sql(lab_data["setup_sql"], lab_data["solution_sql"])
            except LabSetupError as exc:
                raise CommandError(f"«{lab_data['title']}» ({exc.field}) xato: {exc}")

        created = updated = 0
        with transaction.atomic():
            # Ro'yxat eng yangisidan boshlab ko'rsatiladi: 1-laboratoriya yuqorida turishi uchun oxirida qo'shiladi
            for lab_data in reversed(DESIGN_LABS):
                lab = Lab.objects.filter(title=lab_data["title"], author=author).first()
                if lab is None:
                    lab = Lab.objects.create(author=author, **lab_data)
                    created += 1
                elif options["update"]:
                    for field, value in lab_data.items():
                        setattr(lab, field, value)
                    lab.save()
                    updated += 1
                lab.groups.add(*groups)

        skipped = len(DESIGN_LABS) - created - updated
        self.stdout.write(self.style.SUCCESS(f"Qo'shildi: {created}, yangilandi: {updated}, o'zgarishsiz: {skipped}."))
