# 쿼리 파라미터 유효성 검사용 Serializer
from rest_framework import serializers

class RepresentBadgeQuerySerializer(serializers.Serializer):
    badgeID = serializers.IntegerField(required=True, min_value=1)