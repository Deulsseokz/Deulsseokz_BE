from rest_framework import serializers
from .models import Photo, Album

class PhotoRequestSerializer(serializers.ModelSerializer):
    photo = serializers.ImageField(required=True)
    place = serializers.CharField(required=True)
    photoUrl = serializers.URLField(required=False)

    # 설명 관련 필드는 선택 사항
    photoContent = serializers.CharField(required=False, allow_blank=True)
    feelings = serializers.CharField(required=False, allow_blank=True)
    weather = serializers.CharField(required=False, allow_blank=True)
    date = serializers.DateField(required=False)

    def validate(self, data):
        if not data.get("photo") and not data.get("photoUrl"):
            raise serializers.ValidationError("photo 또는 photoUrl 중 하나는 필수입니다.")
        return data

    class Meta:
        model = Photo
        fields = ['photo', 'place', 'photoContent', 'feelings', 'weather', 'date']