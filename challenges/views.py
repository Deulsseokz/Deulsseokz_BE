from rest_framework.views import APIView
from rest_framework import status
from .models import Challenge
from .serializers import ChallengeResponseSerializer, ChallengeAttemptSerializer
from .query_serializers import ChallengeQuerySerializer
from utils.response_wrapper import api_response

# 챌린지 내용 조회
class ChallengeInfoView(APIView):
    def get(self, request):
        query_serializer = ChallengeQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)

        place_name = query_serializer.validated_data['place']

        try:
            challenge = Challenge.objects.select_related('placeId').get(placeId__placeName=place_name)
        except Challenge.DoesNotExist:
            return api_response(
                code = "CHALLENGE_NOT_FOUND",
                message="해당 장소에 대한 챌린지 정보가 없습니다.",
                status_code = status.HTTP_404_NOT_FOUND,
                is_success=False
            )
        response_serializer = ChallengeResponseSerializer(challenge)
        return api_response(result=response_serializer.data)
    
# 챌린지 도전
class ChallengeAttempt(APIView):
    def post(self, request):
        request_data = ChallengeAttemptSerializer(data = request)
        request_data.is_valid(raise_exception=True)

        place = request_data.validated_data['place']
        friends = request_data.validated_data['friends']
        attemptImage = request_data.validated_data['attemptImage']
        attemptDate = request_data.validated_data['attemptDate']