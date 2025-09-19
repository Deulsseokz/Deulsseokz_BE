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
        latest_attempt = self._get_latest_attempt(obj)
        if not latest_attempt:
            return []
        return list(
            ChallengeAttemptUser.objects
            .filter(challengeAttemptId=latest_attempt)
            .values_list('userId__userId', flat=True)
        )

    def get_friendsProfileImage(self, obj):
        latest_attempt = self._get_latest_attempt(obj)
        if not latest_attempt:
            return []
        return list(
            ChallengeAttemptUser.objects
            .filter(challengeAttemptId=latest_attempt)
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