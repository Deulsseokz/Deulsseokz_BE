from rest_framework import serializers
from .models import Photo, Album

class PhotoRequestSerializer(serializers.ModelSerializer):
    photo = serializers.CharField(required=True)
    place = serializers.CharField(required=True)

    # 설명 관련 필드는 선택 사항
    photoContent = serializers.CharField(required=False, allow_blank=True)
    feelings = serializers.CharField(required=False, allow_blank=True)
    weather = serializers.CharField(required=False, allow_blank=True)
    date = serializers.DateField(required=False)

    class Meta:
        model = Photo
        fields = ['photo', 'place', 'photoContent', 'feelings', 'weather', 'date']