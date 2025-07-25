# Generated by Django 5.2.4 on 2025-07-08 14:49

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('places', '0001_initial'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Album',
            fields=[
                ('albumId', models.BigAutoField(primary_key=True, serialize=False)),
                ('placeId', models.ForeignKey(db_column='placeId', on_delete=django.db.models.deletion.CASCADE, related_name='albums', to='places.place')),
                ('userId', models.ForeignKey(db_column='userId', on_delete=django.db.models.deletion.CASCADE, related_name='albums', to='users.user')),
            ],
            options={
                'db_table': 'Album',
            },
        ),
        migrations.CreateModel(
            name='Photo',
            fields=[
                ('photoId', models.BigAutoField(primary_key=True, serialize=False)),
                ('feelings', models.CharField(blank=True, max_length=255, null=True)),
                ('weather', models.CharField(blank=True, max_length=255, null=True)),
                ('photoContent', models.CharField(blank=True, max_length=500, null=True)),
                ('date', models.DateTimeField(blank=True, null=True)),
                ('albumId', models.ForeignKey(db_column='albumId', on_delete=django.db.models.deletion.CASCADE, related_name='photos', to='albums.album')),
            ],
            options={
                'db_table': 'Photo',
            },
        ),
        migrations.AddField(
            model_name='album',
            name='representativePhotoId',
            field=models.ForeignKey(blank=True, db_column='representativePhotoId', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='representative_albums', to='albums.photo'),
        ),
    ]
