# Generated by Django 5.2.4 on 2025-07-30 14:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('points', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='point',
            name='pointUsed',
            field=models.IntegerField(blank=True, db_column='pointUsed', null=True),
        ),
    ]
