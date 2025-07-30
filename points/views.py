import logging
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from rest_framework import status
from .models import User, Point
from utils.response_wrapper import api_response
logger = logging.getLogger(__name__)
from django.conf import settings

from datetime import date

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