# Generated by Django 5.2.4 on 2025-07-30 13:15

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('badges', '0001_initial'),
        ('users', '0003_alter_friendship_receiver_alter_friendship_requester_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='representBadge',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='representBadgeId', to='badges.userbadge'),
        ),
    ]
