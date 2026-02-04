# Generated manually for AI Chatbot integration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myApp', '0012_alter_lesson_slug_and_add_content'),
    ]

    operations = [
        migrations.AddField(
            model_name='lesson',
            name='ai_chatbot_enabled',
            field=models.BooleanField(default=False, help_text='Whether AI chatbot is enabled for this lesson'),
        ),
        migrations.AddField(
            model_name='lesson',
            name='ai_chatbot_webhook_id',
            field=models.CharField(blank=True, help_text='Chatbot webhook ID from training', max_length=200),
        ),
        migrations.AddField(
            model_name='lesson',
            name='ai_chatbot_trained_at',
            field=models.DateTimeField(blank=True, help_text='When transcript was sent for training', null=True),
        ),
        migrations.AddField(
            model_name='lesson',
            name='ai_chatbot_training_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('training', 'Training'),
                    ('trained', 'Trained'),
                    ('failed', 'Failed'),
                ],
                default='pending',
                help_text='Status of AI training',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='lesson',
            name='ai_chatbot_training_error',
            field=models.TextField(blank=True, help_text='Error message if training fails'),
        ),
    ]


