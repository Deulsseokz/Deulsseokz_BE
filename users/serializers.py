from rest_framework import serializers
from .models import User

class MypageInfoSerializer(serializers.ModelSerializer):
    badgeImage = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('userName', 'profileImage', 'badgeImage')

    def get_badgeImage(self, obj):
        try:
            return obj.representBadge.badgeId.badgeImage
        except AttributeError:
            return None