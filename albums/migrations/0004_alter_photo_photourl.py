# Generated by Django 5.2.4 on 2025-07-17 07:41

import albums.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('albums', '0003_alter_photo_photourl'),
    ]

    operations = [
        migrations.AlterField(
            model_name='photo',
            name='photoUrl',
            field=models.ImageField(default='photos/default.jpg', upload_to=albums.models.album_photo_path),
        ),
    ]
