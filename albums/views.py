import logging
from rest_framework.views import APIView
from rest_framework import status
from .models import User, Photo, Album
from .query_serializers import PlaceAlbumSerializer, FavoritePhotoSerializer
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
    
# 장소별 앨범 사진 조회
class PlaceAlbumPictureView(APIView):
    def get(self, request):
        query_serializer = PlaceAlbumSerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        place = query_serializer.validated_data['place']

# 대표 사진 설정
class FavoritePhotoView(APIView):
    def patch(self, request):
        query_serializer = FavoritePhotoSerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        photo = query_serializer.validated_data['photo']

        try:
            photo = Photo.objects.get(photoId = photo)
        except Photo.DoesNotExist:
            api_response(
                code="PHOTO_INVALID",
                message="존재하지 않는 사진입니다."
            )

        Album.objects.update(
            representativePhotoId = photo
        )

        return api_response(
            result=f"{photo}가 대표사진으로 설정되었습니다."
        )


