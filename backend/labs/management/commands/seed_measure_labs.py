"""Pilot uchun AI'siz o'lchov topshiriqlarini (measure_labs.py) bazaga qo'shadi.

Ishga tushirish:
    python manage.py seed_measure_labs --author <o'qituvchi> --group <guruh> [--group ...] [--module <id>]

--module — imtihon rejimidagi modul id si: topshiriqlar shu modulga joylanadi (AI va tuzatilgan yechim o'chadi).
Qayta ishga tushirilsa, bor topshiriqlar takrorlanmaydi: faqat guruhlar qo'shiladi (modul berilsa, joylanadi).
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from users.models import StudentGroup, User

from ...er import DiagramError, validate_diagram
from ...measure_labs import MEASURE_LABS
from ...models import Lab, LabModule


class Command(BaseCommand):
    help = "Pilot uchun izomorf AI'siz ER o'lchov topshiriqlarini qo'shadi"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True, help="Muallif (o'qituvchi yoki admin logini)")
        parser.add_argument("--group", action="append", default=[], help="Biriktiriladigan guruh nomi")
        parser.add_argument("--module", type=int, help="Imtihon rejimidagi modul id si")

    def handle(self, *args, **options):
        try:
            author = User.objects.get(username=options["author"])
        except User.DoesNotExist:
            raise CommandError(f"Bunday foydalanuvchi yo'q: {options['author']}")
        if author.is_student:
            raise CommandError("Muallif talaba bo'la olmaydi.")
        groups = list(StudentGroup.objects.filter(name__in=options["group"]))
        missing = set(options["group"]) - {group.name for group in groups}
        if missing:
            raise CommandError(f"Bunday guruh yo'q: {', '.join(sorted(missing))}")
        module = None
        if options["module"]:
            module = LabModule.objects.filter(pk=options["module"]).first()
            if module is None:
                raise CommandError(f"Modul topilmadi: {options['module']}")
            if module.exam_starts_at is None or module.exam_ends_at is None:
                raise CommandError("Modulda imtihon vaqti belgilanmagan: o'lchov AI'siz bo'lishi uchun uni belgilang.")
        for data in MEASURE_LABS:
            try:
                validate_diagram(data["reference_diagram"])
            except DiagramError as exc:
                raise CommandError(f"«{data['title']}» namunaviy diagrammasida xato: {exc}")

        with transaction.atomic():
            for data in MEASURE_LABS:
                lab = Lab.objects.filter(title=data["title"], author=author).first()
                if lab is None:
                    lab = Lab.objects.create(author=author, module=module, **data)
                    self.stdout.write(self.style.SUCCESS(f"«{lab.title}» qo'shildi (id {lab.pk})."))
                else:
                    if module is not None and lab.module_id != module.pk:
                        lab.module = module
                        lab.save(update_fields=["module"])
                    self.stdout.write(f"«{lab.title}» allaqachon bor (id {lab.pk}): faqat guruhlar qo'shildi.")
                lab.groups.add(*groups)
