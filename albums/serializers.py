from rest_framework import serializers
from .models import Photo, Album

class FavoritePhotoSerializer(serializers.Serializer):
    class Meta:
        albumId = serializers.IntegerField(required=True)
        photoId = serializers.IntegerField(required=True)  