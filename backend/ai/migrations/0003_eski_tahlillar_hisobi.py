"""Hisob yuritilishidan oldingi topshiriq tahlillari tokenlarini AIUsage ga ko'chiradi."""
from django.db import migrations


def backfill(apps, schema_editor):
    AIAnalysis = apps.get_model("ai", "AIAnalysis")
    AIUsage = apps.get_model("ai", "AIUsage")
    analyses = AIAnalysis.objects.filter(completed_at__isnull=False).exclude(input_tokens=0, output_tokens=0)
    AIUsage.objects.bulk_create(
        AIUsage(
            purpose="analysis",
            model_name=analysis.model_name,
            input_tokens=analysis.input_tokens,
            output_tokens=analysis.output_tokens,
            ok=True,
            created_at=analysis.completed_at,
        )
        for analysis in analyses.iterator()
    )


class Migration(migrations.Migration):
    dependencies = [("ai", "0002_ai_sorovlari_hisobi")]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
