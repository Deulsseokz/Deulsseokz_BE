# Generated by Django 5.2.4 on 2025-07-18 02:35

import challenges.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('challenges', '0004_alter_challengeattempt_attemptimage'),
    ]

    operations = [
        migrations.AlterField(
            model_name='challengeattempt',
            name='attemptImage',
            field=models.ImageField(blank=True, max_length=1000, null=True, upload_to=challenges.models.user_place_attempt_path),
        ),
    ]
