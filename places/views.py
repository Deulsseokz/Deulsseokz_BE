import logging
from rest_framework.views import APIView
from rest_framework import status
from .models import User, Place, FavoritePlace
from challenges.models import ChallengeAttempt, ChallengeAttemptUser
from .query_serializers import PlaceAreaSearchQuerySerializer, PlaceQuerySerializer
from .serializers import favoritePlaceSerializer
from utils.response_wrapper import api_response
logger = logging.getLogger(__name__)

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

# 장소 지역 검색
class PlaceAreaSearchView(AuthedAPIView):
    def get(self, request):
        # 토큰 필요 없는 API

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

class FavoritePlaceView(AuthedAPIView):
    # 관심 장소 등록
    def post(self, request):
        app_user = self.get_app_user(request)

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

        if isFavorite is True:
            if not FavoritePlace.objects.filter(userId=app_user, placeId=place).exists():
                FavoritePlace.objects.create(userId=app_user, placeId=place)
            return api_response(
                result=f"{place}가 관심장소에 등록되었습니다."
            )
        else:
            FavoritePlace.objects.filter(
                userId=User.objects.get(userId=app_user),
                placeId=place
            ).delete()
            return api_response(
                result=f"{place}가 관심장소에 삭제되었습니다."
            )

    # 관심 장소 조회
    def get(self, request):
        app_user = self.get_app_user(request)

        favorite_places = FavoritePlace.objects.filter(userId=app_user).select_related('placeId')
        response_list = []

        for favorite in favorite_places:
            place = favorite.placeId

            # 해당 장소에 대한 가장 최근 도전 1개
            latest_attempt = ChallengeAttempt.objects.filter(
                userId=app_user,
                challengeId__placeId=place
            ).select_related('challengeId', 'challengeId__placeId').order_by('-attemptDate').first()

            if latest_attempt:
                friends = ChallengeAttemptUser.objects.filter(challengeAttemptId=latest_attempt)
                friend_ids = [f.userId.userId for f in friends]
                friend_images = [f.userId.profileImage for f in friends]

                response_list.append({
                    "place": place.placeName,
                    "content": latest_attempt.challengeId.content,
                    "friends": friend_ids if friend_ids else None,
                    "friendsProfileImage": friend_images if friend_images else None
                })
            else:
                # 도전 기록이 없을 경우 기본 정보만 반환
                response_list.append({
                    "place": place.placeName,
                    "content": None,
                    "friends": None,
                    "friendsProfileImage": None
                })

        return api_response(
            count=len(response_list),
            result=response_list
        )