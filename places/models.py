from django.db import models
from users.models import User

# Create your models here.
class Place(models.Model):
    placeId = models.BigAutoField(primary_key=True)
    placeName = models.CharField(max_length=255, db_column='placeName')
    area = models.CharField(max_length=255, null=True, blank=True)
    placeImage = models.URLField(null=True, blank=True, db_column='placeImage')
    location = models.JSONField(default=list) # float의 List

    class Meta:
        db_table = 'Place'

    def __str__(self):
        return self.placeName
    
class FavoritePlace(models.Model):
    favoritePlaceId = models.BigAutoField(primary_key=True)
    placeId = models.ForeignKey(Place, on_delete=models.CASCADE, db_column='placeId')
    userId = models.ForeignKey(User, on_delete=models.CASCADE, db_column='userId')

    class Meta:
        db_table = 'FavoritePlace'
        unique_together = ('placeId', 'userId')  # 같은 장소 중복 저장 방지

    def __str__(self):
        return f"{self.userId}의 관심 장소: {self.placeId}"