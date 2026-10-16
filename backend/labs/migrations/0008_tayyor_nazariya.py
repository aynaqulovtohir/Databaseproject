"""Bazada bor tayyor laboratoriyalarga (seed_design_labs) nazariya va namunani qo'shadi.

Faqat nazariyasi bo'sh laboratoriyalar to'ldiriladi: o'qituvchi yozgan matn o'zgarmaydi.
"""
from django.db import migrations


def fill_theory(apps, schema_editor):
    from labs.theory import THEORY

    Lab = apps.get_model("labs", "Lab")
    for title, theory in THEORY.items():
        Lab.objects.filter(title=title, theory="").update(theory=theory)


class Migration(migrations.Migration):
    dependencies = [("labs", "0007_nazariya")]

    operations = [migrations.RunPython(fill_theory, migrations.RunPython.noop)]
