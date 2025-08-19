import logging
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from rest_framework import status
from .models import User, Badge, UserBadge
from .query_serializers import RepresentBadgeQuerySerializer
from utils.response_wrapper import api_response
logger = logging.getLogger(__name__)
from django.conf import settings

# 유저 관련 import
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import NotFound, PermissionDenied

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
    
    # 대표 배지 설정
    def patch(self, request):
        try:
            user = User.objects.get(userId=1)
        except User.DoesNotExist:
            return api_response(
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        query_seriazlier = RepresentBadgeQuerySerializer(data=request.query_params)
        query_seriazlier.is_valid(raise_exception=True)
        badge_id = query_seriazlier.validated_data['badgeID']

        # 유저가 보유하고 있는 배지인지 확인
        try:
            user_badge = UserBadge.objects.select_related("badgeId").get(
                userId=user,
                badgeId_id=badge_id, 
            )
        except UserBadge.DoesNotExist:
            return api_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                result={"code": "USER_BADGE_INVALID", 
                        "message": "보유하지 않는 배지입니다."},
            )
        
        user.representBadge = user_badge
        user.save(update_fields=["representBadge"])

        return api_response(
            result=f"{badge_id} 이/가 대표배지로 설정되었습니다."
        )