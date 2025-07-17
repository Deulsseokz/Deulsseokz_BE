from rest_framework import serializers
from .models import Challenge, ChallengeAttempt

class ChallengeResponseSerializer(serializers.ModelSerializer):
    isFavorite = serializers.SerializerMethodField()

    class Meta:
        model = Challenge
        fields = ('content', 'point', 'condition1', 'condition2', 'condition3', 'isFavorite')

    def get_isFavorite(self, obj):
        return self.context.get('is_favorite', False)
    
class ChallengeAttemptRequestSerializer(serializers.Serializer):
    place = serializers.CharField()
    friends = serializers.CharField(required=False)
    attemptDate = serializers.DateField()
    attemptImage = serializers.ImageField()

class ChallengeAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChallengeAttempt
        fields = ('result', 'resultComment', 'attemptResult', 'attempt')