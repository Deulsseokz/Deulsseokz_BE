from django.db import models
from places.models import Place 
from users.models import User
from challenges.storages import PublicMediaStorage

# Create your models here.
import uuid

def attempt_image_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    user_id = instance.userId.userId
    place_name = instance.challengeId.placeId.placeName.replace(" ", "_")
    return f"{user_id}/{place_name}/{uuid.uuid4().hex}.{ext}"

def user_place_attempt_path(instance, filename):
    ext = filename.split('.')[-1]
    user_id = instance.userId.userId
    place_name = instance.challengeId.placeId.placeName.replace(" ", "_")
    return f"{user_id}/{place_name}/{uuid.uuid4().hex}.{ext}"

class Challenge(models.Model):
    challengeId = models.BigAutoField(primary_key=True)
    placeId = models.ForeignKey(Place, on_delete=models.CASCADE, db_column='placeId')
    point = models.IntegerField(null=True, blank=True)
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
                                     null=True, blank=True)
    resultComment = models.CharField(max_length=255, null=True, blank=True)
    attemptResult = models.BooleanField(null=True)

    class Meta:
        db_table = 'ChallengeAttempt'

    def __str__(self):
        return self.attemptDate

class ChallengeAttemptUser(models.Model):
    challengeAttemptId = models.ForeignKey('ChallengeAttempt', on_delete=models.CASCADE, db_column='challgeAttemptId')
    userId = models.ForeignKey(User, on_delete=models.CASCADE, db_column='userId') 

    class Meta:
        db_table = 'ChallengeAttemptUser'

    def __str__(self):
        return self.userId