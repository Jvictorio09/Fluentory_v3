from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("myApp", "0029_full_rollout_foundation"),
    ]

    operations = [
        migrations.AddField(
            model_name="course",
            name="show_on_v3_landing",
            field=models.BooleanField(
                default=False,
                help_text="Show this course in the V3 landing featured section.",
            ),
        ),
        migrations.AddField(
            model_name="course",
            name="v3_landing_order",
            field=models.PositiveSmallIntegerField(
                default=100,
                help_text="Lower number appears first on V3 landing featured courses.",
            ),
        ),
    ]
