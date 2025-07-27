import logging
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from rest_framework import status
from django.core.files.base import ContentFile
from .models import User, Photo, Album, Place
from .query_serializers import PlaceAlbumSerializer, PhotoSerializer
from .serializers import PhotoRequestSerializer
from utils.response_wrapper import api_response
from rest_framework.parsers import MultiPartParser, FormParser
logger = logging.getLogger(__name__)
from django.conf import settings
from urllib.parse import quote
import requests


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
            photo_urls = []
            for photo in album.photos.all():
                if photo.photoUrl:  # FileField 또는 ImageField라고 가정
                    url = f"{(photo.photoUrl)}"
                    photo_urls.append(url)

            result.append({
                "id": album.albumId,
                "place": album.placeId.placeName,
                "representPhoto": photo_urls
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
                "id": photo.photoId,
                "url": str(photo.photoUrl) if photo.photoUrl else None,
                "feelings": photo.feelings,
                "weather": photo.weather,
                "photoContent": photo.photoContent,
                "date": photo.date,
                "isFavorite": (represent_photo == photo)
        })

        return api_response(
            result=result
        )
    
class PhotoUploadFromUrlView(APIView):
    parser_classes = [JSONParser]

    # url로 사진 추가
    def post(self, request):
        place_name = request.data.get("place")
        photo_url = request.data.get("photo")
        photo_content = request.data.get("photoContent")
        feelings = request.data.get("feelings")
        weather = request.data.get("weather")
        date = request.data.get("date")

        if not photo_url:
            return api_response(
                isSuccess=False,
                code="PHOTO_400",
                message="photoUrl 필드는 필수입니다.",
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(userId=1)
            place = Place.objects.get(placeName=place_name)
            album = Album.objects.get(userId=user, placeId=place)
        except User.DoesNotExist:
            return api_response(code="USER404", message="사용자를 찾을 수 없습니다.", status_code=404)
        except Place.DoesNotExist:
            return api_response(code="PLACE404", message="해당 장소를 찾을 수 없습니다.", status_code=404)
        except Album.DoesNotExist:
            return api_response(code="ALBUM404", message="앨범이 존재하지 않습니다.", status_code=404)

        try:
            response = requests.get(photo_url)
            response.raise_for_status()
            ext = photo_url.split('.')[-1].split('?')[0]
            photo_file = ContentFile(response.content)
            photo_file.name = f"url_upload.{ext}"
        except Exception as e:
            return api_response(
                isSuccess=False,
                code="PHOTO_URL_ERROR",
                message=f"URL에서 이미지를 불러올 수 없습니다: {str(e)}",
                status=status.HTTP_400_BAD_REQUEST
            )

        photo_data = {
            'album': album,
            'photoUrl': photo_file,
        }
        if photo_content:
            photo_data['photoContent'] = photo_content
        if feelings:
            photo_data['feelings'] = feelings
        if weather:
            photo_data['weather'] = weather
        if date:
            photo_data['date'] = date

        photo = Photo.objects.create(**photo_data)

        return api_response(
            result="URL 이미지가 성공적으로 추가되었습니다.",
            data={"photoUrl": photo.photoUrl.url},
            status_code=200
        )

class PhotoView(APIView):
    # 사진 (설명) 추가
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializer = PhotoRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        place_name = validated['place']
        photo_file = validated.get('photo')
        photo_content = validated.get('photoContent')
        feelings = validated.get('feelings')
        weather = validated.get('weather')
        date = validated.get('date')

        print(f"[DEBUG] type={type(photo_file)}, name={getattr(photo_file, 'name', None)}")

        if not photo_file:
            return api_response(
                isSuccess=False,
                code="PHOTO_400",
                message="사진은 반드시 포함되어야 합니다.",
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(userId=1) 
            place = Place.objects.get(placeName=place_name)
            album = Album.objects.get(userId=user, placeId=place)
        except User.DoesNotExist:
            return api_response(code="USER404", message="사용자를 찾을 수 없습니다.", status_code=404)
        except Place.DoesNotExist:
            return api_response(code="PLACE404", message="해당 장소를 찾을 수 없습니다.", status_code=404)
        except Album.DoesNotExist:
            return api_response(code="ALBUM404", message="앨범이 존재하지 않습니다.", status_code=404)

        # 저장 필드 구성
        photo_data = {
            'album': album,
            'photoUrl': photo_file
        }
        if photo_content:
            photo_data['photoContent'] = photo_content
        if feelings:
            photo_data['feelings'] = feelings
        if weather:
            photo_data['weather'] = weather
        if date:
            photo_data['date'] = date

        photo = Photo.objects.create(**photo_data)
        
        logger.info(f"[S3 UPLOADED] name={photo_file.name}, path={photo.photoUrl.name}, url={photo.photoUrl.url}")

        return api_response(
            result="사진이 성공적으로 추가되었습니다.",
            data={"photoUrl": photo.photoUrl.url},
            status_code=200
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


