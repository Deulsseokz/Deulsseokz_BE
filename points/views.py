import logging
from rest_framework.views import APIView
from rest_framework import status
from django.db import transaction
from django.utils import timezone

from .models import User, Point
from utils.response_wrapper import api_response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import NotFound

logger = logging.getLogger(__name__)

# 유저 관련 공통 베이스 뷰
class AuthedAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_app_user(self, request) -> User:
        try:
            return User.objects.get(auth=request.user)
        except User.DoesNotExist:
            raise NotFound("연결된 사용자 프로필이 없습니다.")

class PointView(AuthedAPIView):
    # 포인트 획득/사용 
    @transaction.atomic
    def patch(self, request):
        app_user = self.get_app_user(request)
        today_str = timezone.localdate().isoformat()

        earned  = int(request.data.get('pointEarned') or 0)
        used    = int(request.data.get('pointUsed') or 0)
        content = (request.data.get('content') or '').strip()

        # 음수 입력 방지
        if earned < 0 or used < 0:
            return api_response("pointEarned/pointUsed는 음수일 수 없습니다.", status.HTTP_400_BAD_REQUEST)

        delta = earned - used  # 이번 이벤트 순증감

        # 1) 직전 전체 보유액 
        last_any = (
            Point.objects
            .select_for_update()
            .filter(userId=app_user)
            .order_by('date', 'pointId')  
            .last()
        )
        prev_holding = (last_any.holdingPoint or 0) if last_any else 0

        # 2) 오늘의 직전 누적(러닝 토탈)
        last_today = (
            Point.objects
            .select_for_update()
            .filter(userId=app_user, date=today_str)
            .order_by('pointId')      
            .last()
        )
        prev_today_total = (last_today.todayPoint or 0) if last_today else 0

        new_holding = prev_holding + delta
        if new_holding < 0:
            return api_response("포인트가 부족합니다.", status.HTTP_400_BAD_REQUEST)

        new_today_total = prev_today_total + delta # 해당 날짜 누적

        # 항상 새 튜플 생성
        point = Point.objects.create(
            userId=app_user,
            date=today_str,
            content=content,
            pointEarned=earned,
            pointUsed=used,
            todayPoint=new_today_total,
            holdingPoint=new_holding,
        )

        return api_response(result={
            "pointEarned":  point.pointEarned,
            "pointUsed":    point.pointUsed,
            "content":      point.content,
            "holdingPoint": point.holdingPoint,
            "todayPoint":   point.todayPoint,
            "date":         point.date,
        })

    # 포인트 이력 조회
    def get(self, request):
        app_user = self.get_app_user(request)

        point_qs = Point.objects.filter(userId=app_user).order_by('date', 'pointId')

        if not point_qs.exists():
            return api_response(result={"holdingPoint": 0, "pointLogs": []})

        latest_point = point_qs.last()
        holding_point = latest_point.holdingPoint or 0

        point_logs = [{
            "date": p.date,
            "content": p.content,
            "todayPoint": p.todayPoint if p.todayPoint is not None
                          else ((p.pointEarned or 0) - (p.pointUsed or 0)),
            "pointEarned": p.pointEarned or 0,
            "pointUsed": p.pointUsed or 0,
        } for p in point_qs]

        return api_response(result={
            "holdingPoint": holding_point,
            "pointLogs": point_logs,
        })
