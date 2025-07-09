from rest_framework import serializers
from .models import Challenge, ChallengeAttempt

class ChallengeResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Challenge
        fields = ('content', 'point', 'condition1', 'condition2', 'condition3')

class ChallengeAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChallengeAttempt
        fields = ('result', 'resultComment', 'attemptResult', 'attempt')