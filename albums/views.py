import logging
from rest_framework.views import APIView
from rest_framework import status
from .models import User, Photo, Album
from .query_serializers import PlaceAlbumSerializer, PhotoSerializer
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

class PhotoView(APIView):
    # 사진 삭제 
    def delete(self, request):
        query_serializer = PhotoSerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        photoId = query_serializer.validated_data['photoId']

        try:
            deletePhoto = Photo.objects.get(photoId = photoId)
        except Photo.DoesNotExist:
            logger.info(f"[FAILED DELETE PHOTO] photoId={photoId} not found")
            return api_response(
                code="PHOTO_INVALID",
                message="존재하지 않는 사진입니다."
            )

        deletePhoto.delete()

        return api_response(
            result=f"사진이 성공적으로 삭제되었습니다."
        )

# 대표 사진 설정
class FavoritePhotoView(APIView):
    def patch(self, request):
        query_serializer = PhotoSerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        photoId = query_serializer.validated_data['photoId']

        try:
            representPhoto = Photo.objects.get(photoId = photoId)
        except Photo.DoesNotExist:
            return api_response(
                code="PHOTO_INVALID",
                message="존재하지 않는 사진입니다."
            )

        album = representPhoto.album # photo에서 외래키 연결되어있음
        album.representativePhotoId = representPhoto
        album.save()

        return api_response(
            result=f"{representPhoto} 이/가 대표사진으로 설정되었습니다."
        )


