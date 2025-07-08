from django.db import models
from users.models import User
from places.models import Place

# Create your models here.
class Point(models.Model):
    pointId = models.BigAutoField(primary_key=True)

    userId = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='userId',
        related_name='points'
    )

    placeId = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        db_column='placeId',
        related_name='points'
    )

    date = models.CharField(max_length=250, null=True, blank=True)

    pointEarned = models.IntegerField(
        null=True,
        blank=True,
        db_column='pointEarned'
    )

    todayPoint = models.IntegerField(
        null=True,
        blank=True,
        db_column='todayPoint'
    )

    holdingPoint = models.IntegerField(
        null=True,
        blank=True,
        db_column='holdingPoint'
    )

    class Meta:
        db_table = 'Point'

    def __str__(self):
        return self.date