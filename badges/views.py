import logging
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from rest_framework import status
from .models import User, UserBadge
from utils.response_wrapper import api_response
logger = logging.getLogger(__name__)
from django.conf import settings

from rest_framework.permissions import AllowAny
# Create your views here.
class BadgeView(APIView):
    permission_classes = [AllowAny]
    # 획득 배지 조회
    def get(self, request):
        try:
            user = User.objects.get(userId=1)
        except User.DoesNotExist:
            return api_response(
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        user_badges = UserBadge.objects.filter(userId=user).select_related("badgeId")

        result = []
        for user_badge in user_badges:
            badge = user_badge.badgeId  
            result.append({
                "badgeId": badge.badgeId,
                "badgeName": badge.badgeName,
                "badgeImage": badge.badgeImage,
                "condition": badge.condition,
                "createdAt": user_badge.createdAt.strftime("%Y-%m-%d"),
                "isRepresent": (user.representBadge_id == user_badge.pk)
            })

        return api_response(
            result=result
        )
        