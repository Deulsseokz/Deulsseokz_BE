from django.db import models
from places.models import Place 
from users.models import User
from challenges.storages import PublicMediaStorage

# Create your models here.
import uuid
import unicodedata
import re

def attempt_image_upload_path(instance, filename):
    # 폴더명으로 사용할 수 없는 특수문자 등을 정리하는 함수
    def sanitize_folder_name(name: str) -> str:
        # 유니코드 정규화 (예: 'ㄱ' + 'ㅏ' -> '가')
        name = unicodedata.normalize("NFKD", name)
        # 안전한 문자(알파벳, 숫자, 공백, 하이픈, 한글)만 남기고 제거
        name = re.sub(r"[^\w\s\-가-힣]", "", name)
        # 양쪽 공백 제거 후, 내부 공백은 밑줄(_)로 변경
        return name.strip().replace(" ", "_")
    
    # 인스턴스에서 정보 추출
    user_id = instance.userId.userId
    place_name = sanitize_folder_name(instance.challengeId.placeId.placeName)
    
    # 파일 확장자 추출
    ext = filename.split('.')[-1]
    
    # 하이픈(-)이 포함된 고유한 파일명 생성
    unique_filename = f"{uuid.uuid4()}.{ext}"
    
    return f"{user_id}/{place_name}/{unique_filename}"

def user_place_attempt_path(instance, filename):
    ext = filename.split('.')[-1]
    user_id = instance.userId.userId
    place_name = instance.challengeId.placeId.placeName.replace(" ", "_")
    return f"{user_id}/{place_name}/{uuid.uuid4().hex}.{ext}"

class Challenge(models.Model):
    challengeId = models.BigAutoField(primary_key=True)
    placeId = models.ForeignKey(Place, on_delete=models.CASCADE, db_column='placeId')
    point = models.CharField(max_length=255, null=True, blank=True)
    content = models.CharField(max_length=255, null=True, blank=True)
    condition1 = models.CharField(max_length=255, null=True, blank=True)
    condition2 = models.CharField(max_length=255, null=True, blank=True)
    condition3 = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'Challenge'

    def __str__(self):
        return self.content

class ChallengeAttempt(models.Model):
    challengeAttemptId = models.BigAutoField(primary_key=True)
    challengeId = models.ForeignKey(Challenge, on_delete=models.CASCADE, db_column='challengeId')
    userId = models.ForeignKey(User, on_delete=models.CASCADE, db_column='userId')
    attemptDate = models.CharField(max_length=255, null=True, blank=True)
    attemptImage = models.ImageField(upload_to=attempt_image_upload_path, 
                                     storage=PublicMediaStorage,
                                     null=True, blank=True, max_length=2048)
    resultComment = models.TextField(blank=True, null=True) 
    attemptResult = models.BooleanField(null=True)
    result_details = models.JSONField(null=True, blank=True)

    class AttemptStatus(models.TextChoices):
        PENDING = 'PENDING', '처리 대기중'
        PROCESSING = 'PROCESSING', '처리중'
        SUCCESS = 'SUCCESS', '성공'
        FAILED = 'FAILED', '실패'

    status = models.CharField(
        max_length=15,
        choices=AttemptStatus.choices,
        default=AttemptStatus.PENDING
    )

    class Meta:
        db_table = 'ChallengeAttempt'

    def __str__(self):
        return self.attemptDate

class ChallengeAttemptUser(models.Model):
    challengeAttemptId = models.ForeignKey('ChallengeAttempt', on_delete=models.CASCADE, db_column='challengeAttemptId')
    userId = models.ForeignKey(User, on_delete=models.CASCADE, db_column='userId') 

    class Meta:
        db_table = 'ChallengeAttemptUser'

    def __str__(self):
        return self.userId