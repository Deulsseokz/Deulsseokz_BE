import os
from celery import Celery

# Django settings 모듈을 Celery의 기본으로 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# Django 설정 파일로부터 Celery 설정을 불러옴
app.config_from_object('django.conf:settings', namespace='CELERY')

# 등록된 모든 Django 앱에서 task 모듈을 자동으로 찾음
app.autodiscover_tasks()