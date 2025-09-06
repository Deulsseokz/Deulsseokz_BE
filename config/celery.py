import os
from celery import Celery

# Celery를 위해 기본 Django settings 모듈을 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

app.config_from_object('django.conf:settings', namespace='CELERY')

# 등록된 모든 Django 앱 설정에서 task 모듈을 자동으로 로드
app.autodiscover_tasks()