import logging
from rest_framework.views import APIView
from rest_framework import status
from .models import User, Photo, Album
from .query_serializers import PlaceAlbumSerializer
from utils.response_wrapper import api_response
logger = logging.getLogger(__name__)

# 앨범 목록 조회
class AlbumListView(APIView):
    def get(self, request):
        try:
            user = User.objects.get(userId=1)
        except User.DoesNotExist:
            return api_response(
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        album_lists = Album.objects.filter(userId=user).select_related('placeId')

        if not album_lists.exists():
            return api_response(
                is_success=True,
                code='COMMON200',
                message='앨범이 없습니다.',
                status_code=status.HTTP_200_OK
            )
        
        album_lists_name = [al.placeId.placeName for al in album_lists]

        return api_response(
            result=album_lists_name
        )