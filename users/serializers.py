from rest_framework import serializers
from .models import User

class MypageInfoSerializer(serializers.ModelSerializer):
    badgeId = serializers.IntegerField(source='representBadge_id', read_only=True)

    class Meta:
        model = User
        fields = ('userName', 'profileImage', 'badgeId')