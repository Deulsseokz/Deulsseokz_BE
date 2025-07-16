import boto3
from urllib.parse import quote
from django.conf import settings
import logging
from rest_framework.views import APIView
from rest_framework import status
from .models import User, Place, FavoritePlace
from challenges.models import ChallengeAttempt, ChallengeAttemptUser
from .query_serializers import PlaceAreaSearchQuerySerializer, PlaceQuerySerializer
from .serializers import favoritePlaceSerializer
from utils.response_wrapper import api_response
logger = logging.getLogger(__name__)

# s3 검색
def get_place_image_url(place_name: str) -> str | None:
    s3 = boto3.client('s3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )

    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    prefix = f"place-images/{place_name}"  # 확장자 제외

    response = s3.list_objects_v2(
        Bucket=bucket_name,
        Prefix=prefix
    )

    if "Contents" not in response:
        return None

    # 첫 번째 매칭 파일의 key 가져오기
    for obj in response["Contents"]:
        key = obj["Key"]
        if key.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            encoded_key = quote(key)
            return f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{encoded_key}"

    return None

# 장소 지역 검색
class PlaceAreaSearchView(APIView):
    def get(self, request):
        query_serializer = PlaceAreaSearchQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        area = query_serializer.validated_data['area']

        places = Place.objects.filter(area__icontains=area).values_list('placeName', flat=True) # 튜플 리스트로 반환 옵션

        if not places:
            return api_response(
                is_success=False,
                code='PLACE_IS_NOT_VALID',
                message='해당 지역의 장소 정보가 존재하지 않습니다.',
                status_code = status.HTTP_404_NOT_FOUND
            )
        
        return api_response(
            result={'place': list(places)}
        )

class FavoritePlaceView(APIView):
    # 관심 장소 등록
    def post(self, request):
        serializer = favoritePlaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        place = validated['place']
        isFavorite = validated['isFavorite']

        try:
            place = Place.objects.get(placeName = place)
        except Place.DoesNotExist:
            return api_response(
                code="LOCATION_INVALID",
                message="장소에 대한 정보가 존재하지 않습니다."
            )
        
        user = User.objects.get(userId = 1)

        if isFavorite is True:
            if not FavoritePlace.objects.filter(userId=user, placeId=place).exists():
                FavoritePlace.objects.create(userId=user, placeId=place)
            return api_response(
                result=f"{place}가 관심장소에 등록되었습니다."
            )
        else:
            FavoritePlace.objects.filter(
                userId=User.objects.get(userId=1),
                placeId=place
            ).delete()
            return api_response(
                result=f"{place}가 관심장소에 삭제되었습니다."
            )

    # 관심 장소 조회
    def get(self, request):
        try:
            user = User.objects.get(userId=1)
        except User.DoesNotExist:
            return api_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="유저를 찾을 수 없습니다.",
                is_success=False
            )

        favorite_places = FavoritePlace.objects.filter(userId=user).select_related('placeId')
        response_list = []

        for favorite in favorite_places:
            place = favorite.placeId
            image_url = get_place_image_url(place.placeName)

            # 해당 장소에 대한 가장 최근 도전 1개
            latest_attempt = ChallengeAttempt.objects.filter(
                userId=user,
                challengeId__placeId=place
            ).select_related('challengeId', 'challengeId__placeId').order_by('-attemptDate').first()

            if latest_attempt:
                friends = ChallengeAttemptUser.objects.filter(challengeAttemptId=latest_attempt)
                friend_ids = [f.userId.userId for f in friends]
                friend_images = [f.userId.profileImage for f in friends]

                response_list.append({
                    "place": place.placeName,
                    "placeImage": image_url,
                    "content": latest_attempt.challengeId.content,
                    "friends": friend_ids if friend_ids else None,
                    "friendsProfileImage": friend_images if friend_images else None
                })
            else:
                # 도전 기록이 없을 경우 기본 정보만 반환
                response_list.append({
                    "place": place.placeName,
                    "placeImage": image_url,
                    "content": None,
                    "friends": None,
                    "friendsProfileImage": None
                })

        return api_response(
            count=len(response_list),
            result=response_list
        )