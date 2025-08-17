from rest_framework import serializers
from .models import User

class MypageInfoSerializer(serializers.ModelSerializer):
    badgeId = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('userName', 'profileImage', 'badgeId')

    def get_badgeId(self, obj):
        try:
            return obj.representBadge.badgeId
        except AttributeError:
            return None