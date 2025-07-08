from django.db import models
from users.models import User

# Create your models here.
class Badge(models.Model):
    badgeId = models.BigAutoField(primary_key=True)
    badgeName = models.CharField(max_length=255, null=True, blank=True)
    badgeImage = models.URLField(null=True, blank=True)
    condition = models.IntegerField(
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'Badge'

    def __str__(self):
        return self.badgeName 


class UserBadge(models.Model):
    userBadgeId = models.BigAutoField(primary_key=True)
    userId = models.ForeignKey(User, on_delete=models.CASCADE, db_column='userId')
    badgeId = models.ForeignKey(Badge, on_delete=models.CASCADE, db_column='badgeId')

    class Meta:
        db_table = 'UserBadge'
        unique_together = ('userId', 'badgeId') # 중복 획득 방지

    def __str__(self):
        return f"{self.userId}의 뱃지: {self.badgeId}"