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

# 유저 관련 공통 베이스 뷰
class AuthedAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_app_user(self, request) -> User:
        try:
            return User.objects.get(auth=request.user)
        except User.DoesNotExist:
            raise NotFound("연결된 사용자 프로필이 없습니다.")

# Create your views here.
class BadgeView(AuthedAPIView):
    # 획득 배지 조회
    def get(self, request):
        app_user = self.get_app_user(request)
        
        user_badges = UserBadge.objects.filter(userId=app_user).select_related("badgeId")

        result = []
        for user_badge in user_badges:
            badge = user_badge.badgeId  
            result.append({
                "badgeId": badge.badgeId,
                "badgeName": badge.badgeName,
                "badgeImage": badge.badgeImage,
                "condition": badge.condition,
                "createdAt": user_badge.createdAt.strftime("%Y-%m-%d"),
                "isRepresent": (app_user.representBadge_id == user_badge.pk)
            })

        return api_response(
            result=result
        )
    
    # 대표 배지 설정
    def patch(self, request):
        app_user = self.get_app_user(request)
        
        query_seriazlier = RepresentBadgeQuerySerializer(data=request.query_params)
        query_seriazlier.is_valid(raise_exception=True)
        badge_id = query_seriazlier.validated_data['badgeID']

        # 유저가 보유하고 있는 배지인지 확인
        try:
            user_badge = UserBadge.objects.select_related("badgeId").get(
                userId=app_user,
                badgeId_id=badge_id, 
            )
        except UserBadge.DoesNotExist:
            return api_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                result={"code": "USER_BADGE_INVALID", 
                        "message": "보유하지 않는 배지입니다."},
            )
        
        app_user.representBadge = user_badge
        app_user.save(update_fields=["representBadge"])

        return api_response(
            result=f"{badge_id} 이/가 대표배지로 설정되었습니다."
        )