# Generated by Django 5.2.4 on 2025-07-16 17:57

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_remove_user_neighborstatus_remove_user_receiverid_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='friendship',
            name='receiver',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='received_friend_requests', to='users.user'),
        ),
        migrations.AlterField(
            model_name='friendship',
            name='requester',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_friend_requests', to='users.user'),
        ),
        migrations.AlterField(
            model_name='friendship',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected'), ('blocked', 'Blocked')], db_column='status', default='pending', max_length=10),
        ),
    ]
