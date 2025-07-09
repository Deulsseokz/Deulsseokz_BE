from rest_framework import serializers
from .models import Challenge

class ChallengeResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Challenge
        fields = ('content', 'point', 'condition1', 'condition2', 'condition3')