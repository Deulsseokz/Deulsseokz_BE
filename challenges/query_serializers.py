# 쿼리 파라미터 유효성 검사용 Serializer
from rest_framework import serializers

class ChallengeQuerySerializer(serializers.Serializer):
    place = serializers.CharField(required = True)