# Generated migration for TeacherRequest model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('myApp', '0021_lead_leadenrollmentlink_leadgiftlink_leadtimeline_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='TeacherRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('email', models.EmailField(max_length=254)),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('bio', models.TextField(help_text='Brief bio and teaching experience')),
                ('qualifications', models.TextField(help_text='Educational background and certifications')),
                ('languages_spoken', models.CharField(help_text='Languages you can teach (comma-separated)', max_length=200)),
                ('teaching_experience', models.TextField(help_text='Years of experience and areas of expertise')),
                ('motivation', models.TextField(help_text='Why do you want to teach on this platform?')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('admin_notes', models.TextField(blank=True, help_text='Internal notes for admin review')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_teacher_requests', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='teacherrequest',
            index=models.Index(fields=['status'], name='myApp_teach_status_idx'),
        ),
        migrations.AddIndex(
            model_name='teacherrequest',
            index=models.Index(fields=['created_at'], name='myApp_teach_created_idx'),
        ),
    ]

