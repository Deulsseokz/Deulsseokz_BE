from rest_framework import serializers
from .models import Challenge, ChallengeAttempt, ChallengeAttemptUser

class ChallengeResponseSerializer(serializers.ModelSerializer):
    placeName = serializers.SerializerMethodField()
    isFavorite = serializers.SerializerMethodField()
    friends = serializers.SerializerMethodField()
    friendsProfileImage = serializers.SerializerMethodField()

    class Meta:
        model = Challenge
        fields = ('placeName', 'content', 'point', 'condition1', 'condition2', 'condition3', 'isFavorite', 'friends',
            'friendsProfileImage')

    def get_placeName(self, obj):
        return obj.placeId.placeName

    def get_isFavorite(self, obj):
        return self.context.get('is_favorite', False)
    
    def get_friends(self, obj):

        # 현재 사용자의 ID 가져오기 
        current_user_id = self.context.get('current_user_id')
        if not current_user_id:
            return []
        
        latest_attempt = self._get_latest_attempt(obj)
        if not latest_attempt:
            return []
        return list(
            ChallengeAttemptUser.objects
            .filter(challengeAttemptId=latest_attempt)
            .exclude(userId__userId=current_user_id)
            .values_list('userId__userId', flat=True)
        )

    def get_friendsProfileImage(self, obj):

        current_user_id = self.context.get('current_user_id')
        if not current_user_id:
            return []
        
        latest_attempt = self._get_latest_attempt(obj)
        if not latest_attempt:
            return []
        return list(
            ChallengeAttemptUser.objects
            .filter(challengeAttemptId=latest_attempt)
            .exclude(userId__userId=current_user_id)
            .values_list('userId__profileImage', flat=True)
        )

    def _get_latest_attempt(self, challenge):
        return ChallengeAttempt.objects \
            .filter(challengeId=challenge) \
            .order_by('-attemptDate') \
            .first()
    
class ChallengeAttemptRequestSerializer(serializers.Serializer):
    place = serializers.CharField()
    friends = serializers.CharField(required=False)
    attemptDate = serializers.DateField()
    attemptImage = serializers.ImageField()

class ChallengeAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChallengeAttempt
        fields = ('result', 'resultComment', 'attemptResult', 'attempt')