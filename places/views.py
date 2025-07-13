import logging
from rest_framework.views import APIView
from rest_framework import status
from .models import User, Place, FavoritePlace
from .query_serializers import PlaceAreaSearchQuerySerializer, PlaceQuerySerializer
from utils.response_wrapper import api_response
logger = logging.getLogger(__name__)

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

# 관심 장소 등록
class FavoritePlacePostView(APIView):
    def post(self, request):
        query_serializer = PlaceQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        place = query_serializer.validated_data['place']

        try:
            place = Place.objects.get(placeName = place)
        except Place.DoesNotExist:
            api_response(
                code="LOCATION_INVALID",
                message="장소에 대한 정보가 존재하지 않습니다."
            )

        FavoritePlace.objects.create(
            userId = User.objects.get(userId=1),
            placeId = place
        )

        return api_response(
            result=f"{place}가 관심장소에 등록되었습니다."
        )