import logging
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from rest_framework import status
from .models import User
from utils.response_wrapper import api_response
logger = logging.getLogger(__name__)
from django.conf import settings


class PointView(APIView):
    # 포인트 사용(획득 및 사용)
    def patch(self, request):
        try: 
            user = User.objects.get(userId=1)
        except User.DoesNotExist:
            return api_response(
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # null 아닌 필드만 업데이트
        update_fields = ['point_earned', 'point_used']
        for field in update_fields:
            if field in request.data[field] is not None:
                setattr(point)
