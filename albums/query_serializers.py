from rest_framework import serializers

class PlaceAlbumSerializer(serializers.Serializer):
    place = serializers.CharField(required = True)

class FavoritePhotoSerializer(serializers.Serializer):
    photo = serializers.CharField(required = True)