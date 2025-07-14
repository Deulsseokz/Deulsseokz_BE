import logging
from rest_framework.views import APIView
from rest_framework import status
from .models import User, Photo, Album, Place
from .query_serializers import PlaceAlbumSerializer, PhotoSerializer
from .serializers import PhotoRequestSerializer
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
        
        albums = Album.objects.filter(userId=user).select_related('placeId', 'representativePhotoId').prefetch_related('photos')

        if not albums.exists():
            return api_response(
                is_success=True,
                code='COMMON200',
                message='앨범이 없습니다.',
                status_code=status.HTTP_200_OK
            )
        
        result = []
        for album in albums:
            photo = album.representativePhotoId
            photo_url = photo.photoUrl if photo else None

            result.append({
                "place": album.placeId.placeName,
                "representPhoto": photo_url
            })

        return api_response(
            result=result
        )
    
# 장소별 앨범 사진 조회
class PlaceAlbumPictureView(APIView):
    def get(self, request):
        query_serializer = PlaceAlbumSerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        place = query_serializer.validated_data['place']

        user = User.objects.get(userId=1)
        try:
            place = Place.objects.get(placeName=place)
        except Place.DoesNotExist:
            return api_response(
                code="PLACE404",
                message="해당 장소를 찾을 수 없습니다.",
                status=status.HTTP_404_NOT_FOUND
            )
        
        try: 
            album = Album.objects.get(userId=1, placeId=place)
        except Album.DoesNotExist:
            return api_response(
                code="ALBUM404",
                message="앨범이 존재하지 않습니다.",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # 사진 조회
        photos = Photo.objects.filter(album=album)
        represent_photo = album.representativePhotoId

        result = []
        for photo in photos:
            result.append({
                "url": photo.photoUrl if photo.photoUrl else None,
                "feelings": photo.feelings,
                "weather": photo.weather,
                "photoContent": photo.photoContent,
                "date": photo.date,
                "isFavorite": (represent_photo == photo)
        })

        return api_response(
            result=result
        )

class PhotoView(APIView):
    # 사진 (설명) 추가
    def post(self, request):
        serializer = PhotoRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        placeName = validated['place']
        photoFile = validated.get('photo')
        
        # 선택적 필드 (설명 관련)
        photoContent = validated.get('photoContent')
        feelings = validated.get('feelings')
        weather = validated.get('weather')
        date = validated.get('date')

        if not photoFile:
            return api_response(
                isSuccess=False,
                code="PHOTO_400",
                message="사진은 반드시 포함되어야 합니다.",
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.get(userId=1)
        
        try:
            place = Place.objects.get(placeName=placeName)
        except Place.DoesNotExist:
            return api_response(
                code="PLACE404",
                message="해당 장소를 찾을 수 없습니다.",
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            album = Album.objects.get(userId=user, placeId=place)
        except Album.DoesNotExist:
            return api_response(
                code="ALBUM404",
                message="앨범이 존재하지 않습니다.",
                status_code=status.HTTP_404_NOT_FOUND
            )

        # 상황 1: 사진만 추가
        if not all([photoContent, feelings, weather, date]):
            Photo.objects.create(
                album=album,
                photoUrl=photoFile
            )
            return api_response(
                result="사진이 성공적으로 추가되었습니다.",
                status_code=status.HTTP_200_OK
            )

        # 상황 2: 사진과 설명 같이 추가
        Photo.objects.create(
            album=album,
            photoUrl=photoFile,
            photoContent=photoContent,
            feelings=feelings,
            weather=weather,
            date=date
        )
        return api_response(
            result="사진과 설명이 성공적으로 추가되었습니다.",
            status_code=status.HTTP_200_OK
        )
    
    # 사진 (설명) 수정
    def patch(self, request):
        user = User.objects.get(userId=1)
        photoId = request.data.get('photoId')
        # 사진 조회
        try:
            photo = Photo.objects.get(photoId=photoId, album__userId=user)
        except Photo.DoesNotExist:
            return api_response(
                isSuccess=False,
                code="PHOTO404",
                message="해당 사진을 찾을 수 없습니다.",
                status_code=status.HTTP_404_NOT_FOUND
            )

        # null이 아닌 필드만 업데이트
        update_fields = ['feelings', 'weather', 'photoContent', 'date']
        for field in update_fields:
            if field in request.data and request.data[field] is not None:
                setattr(photo, field, request.data[field])

        photo.save()

        return api_response(
            result="사진 정보가 성공적으로 수정되었습니다.",
            status_code=status.HTTP_200_OK
        )

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


