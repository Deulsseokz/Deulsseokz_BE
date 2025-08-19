import logging
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from rest_framework import status
from .models import User, Point
from utils.response_wrapper import api_response
logger = logging.getLogger(__name__)
from django.conf import settings

from datetime import date

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

class PointView(APIView):
    # 포인트 사용(획득 및 사용)
    def patch(self, request):
        try: 
            user = User.objects.get(userId=1)
        except User.DoesNotExist:
            return api_response(
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # 오늘 날짜
        today_str = date.today().isoformat()

        # 오늘 날짜에 해당하는 포인트 객체 가져오거나 생성
        point, created = Point.objects.get_or_create(userId=user, date=today_str)

        earned = request.data.get('pointEarned')
        used = request.data.get('pointUsed')
        content = request.data.get('content')

        # 기존 holdingPoint
        prev_hodling = point.holdingPoint or 0

        # 변경 값 계산
        if earned is not None:
            point.pointEarned = earned
        if used is not None:
            point.pointUsed = used
        if content is not None:
            point.content = content

        delta = (earned or 0) - (used or 0)
        point.holdingPoint = prev_hodling + delta
        point.todayPoint = point.holdingPoint

        point.save()

        return api_response(
            result={
                "pointEarned": point.pointEarned,
                "pointUsed": point.pointUsed,
                "content": point.content,
                "holdingPoint": point.holdingPoint,
                "todayPoint": point.todayPoint,
                "date": point.date
            }
        )
    
    # 포인트 이력 조회
    def get(self, request):
        try: 
            user = User.objects.get(userId=1)
        except User.DoesNotExist:
            return api_response(
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        point_qs = Point.objects.filter(userId=user).order_by('date')

        if not point_qs.exists():
            return api_response(result={
                                    "holdingPoint": 0,
                                    "pointLogs": []
                                })
        
        # 유저의 전체 홀딩 포인트 = 가장 마지막 항목의 홀딩 포인트
        latest_point = point_qs.last()
        holding_point = latest_point.holdingPoint or 0

        point_logs = []
        for point in point_qs:
            point_logs.append({
                "date": point.date,
                "content": point.content,
                "todayPoint": point.todayPoint or 0,
                "pointEarned": point.pointEarned or 0,
                "pointUsed": point.pointUsed or 0
            })

        return api_response(
            result={
                "holdingPoint": holding_point,
                "pointLogs": point_logs
            }
        )