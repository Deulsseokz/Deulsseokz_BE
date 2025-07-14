from rest_framework import serializers

class PlaceAlbumSerializer(serializers.Serializer):
    place = serializers.CharField(required = True)

class PhotoSerializer(serializers.Serializer):
    photoId = serializers.CharField(required = True)