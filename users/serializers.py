from rest_framework import serializers
from .models import User
from challenges.models import ChallengeAttempt, Challenge

class MypageInfoSerializer(serializers.ModelSerializer):
    badgeId = serializers.IntegerField(source='representBadge_id', read_only=True)
    success = serializers.SerializerMethodField()
    conquer = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'userName', 
            'profileImage', 
            'badgeId', 
            'success', 
            'conquer'
        )

    def get_success(self, obj):
        return ChallengeAttempt.objects.filter(
            userId=obj, 
            status=ChallengeAttempt.AttemptStatus.SUCCESS
        ).count()

    def get_conquer(self, obj):
        success_count = self.get_success(obj)
        total_challenges = Challenge.objects.count()

        if total_challenges == 0:
            return 0.0  # ZeroDivisionError 방지

        return round((success_count / total_challenges), 2)