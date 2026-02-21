# Generated manually to fix null constraint issue

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myApp', '0024_course_certificate_field_positions'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='preview_video_url',
            field=models.URLField(blank=True, null=True, help_text='Optional preview/promo video URL (YouTube, Vimeo, etc.)'),
        ),
    ]

