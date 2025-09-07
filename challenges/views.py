import requests
import logging
import re
import json
from django.core.files.base import ContentFile
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.views import APIView
from rest_framework import status
from .models import User, Challenge, ChallengeAttempt, ChallengeAttemptUser
from albums.models import Album, Photo
from places.models import FavoritePlace
from .serializers import ChallengeResponseSerializer, ChallengeAttemptRequestSerializer, ChallengeAttemptSerializer
from .query_serializers import ChallengeQuerySerializer
from utils.response_wrapper import api_response
from django.db import transaction
from .tasks import process_challenge_attempt
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

# 전체 챌린지 목록 조회
class ChallengeListView(AuthedAPIView):
    def get(self, request):
        app_user = self.get_app_user(request)
        
        result = []
        challenges = Challenge.objects.all()

        for challenge in challenges:
            # 해당 유저의 성공한 도전 이력이 있는지 확인
            attempt = ChallengeAttempt.objects.filter(
                userId=app_user,
                challengeId=challenge,
                attemptResult=True
            ).order_by('-attemptDate').first()

            result.append({
                "challengeId": challenge.challengeId,
                "placeName": challenge.placeId.placeName,
                "isChallenged": attempt is not None,
                "challengePhoto": attempt.attemptImage.url if attempt else None,
                "location": challenge.placeId.location
            })

        return api_response(
            result=result
        )

# 챌린지 정보 조회
class ChallengeInfoView(AuthedAPIView):
    def get(self, request):
        app_user = self.get_app_user(request)

        query_serializer = ChallengeQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)

        validated_data = query_serializer.validated_data
        placeName = validated_data.get('place', None)
        placeId = validated_data.get('placeId', None)

        if not placeName and not placeId:
            return api_response(
                code="INVALID_QUERY",
                message="place 또는 placeId 중 하나는 필수입니다.",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # Case 1: placeId 기반 단일 조회
        if placeId:
            challenges = Challenge.objects.select_related('placeId').filter(placeId__placeId=placeId)

            if not challenges.exists():
                return api_response(
                    code="CHALLENGE_NOT_FOUND",
                    message="해당 ID에 대한 챌린지 정보가 없습니다.",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            favorite_place_ids = set(
                FavoritePlace.objects.filter(userId=app_user).values_list('placeId', flat=True)
            )

            result = []
            for challenge in challenges:
                placeName = challenge.placeId.placeName
                is_favorite = challenge.placeId.placeId in favorite_place_ids
                serializer = ChallengeResponseSerializer(challenge, context={'is_favorite': is_favorite})
                result.append(serializer.data)

            return api_response(result=result)

        # Case 2: placeName 기반 다중 조회
        else:
            challenges = Challenge.objects.select_related('placeId').filter(placeId__placeName__icontains=placeName)

            if not challenges.exists():
                return api_response(
                    code="CHALLENGE_NOT_FOUND",
                    message=f"'{placeName}'을 포함하는 장소에 대한 챌린지가 없습니다.",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            favorite_place_ids = set(
                FavoritePlace.objects.filter(userId=app_user).values_list('placeId', flat=True)
            )

            result = []
            for challenge in challenges:
                placeName = challenge.placeId.placeName
                is_favorite = challenge.placeId.placeId in favorite_place_ids
                serializer = ChallengeResponseSerializer(challenge, context={'is_favorite': is_favorite})
                result.append(serializer.data)

            return api_response(result=result)

# 챌린지 도전
class ChallengeAttemptView(AuthedAPIView):
    @swagger_auto_schema(request_body=ChallengeAttemptRequestSerializer)
    def post(self, request):
        app_user = self.get_app_user(request)

        serializer = ChallengeAttemptRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        place = data.get('place')
        attemptImage = data.get('attemptImage')
        attemptDate = data.get('attemptDate')
        friend_ids = data.get('friends', []) # 친구 ID 리스트를 여기서 파싱합

        try:
            challenge = Challenge.objects.get(placeId__placeName=place)
        except Challenge.DoesNotExist:
            return api_response(
                code="CHALLENGE_NOT_FOUND",
                message=f"장소 '{place}'에 해당하는 챌린지가 없습니다.",
                status_code=status.HTTP_404_NOT_FOUND
            )

        # "처리 대기중" 상태의 메인 레코드(요청자 기준)를 하나 생성
        main_attempt = ChallengeAttempt.objects.create(
            challengeId=challenge,
            userId=app_user,
            attemptImage=attemptImage,
            attemptDate=attemptDate,
            status=ChallengeAttempt.AttemptStatus.PENDING
        )
        # Celery Task 호출 시, 메인 시도 ID와 함께 친구 ID 리스트를 전달
        process_challenge_attempt.delay(main_attempt.pk, friend_ids)

        logger.info(f"챌린지 시도 ID {main_attempt.pk} (친구 {len(friend_ids)}명 포함)가 큐에 추가됨.")

        # 사용자에게는 즉시 응답을 보냄
        return api_response(
            code="CHALLENGE_SUBMITTED",
            message="챌린지 사진을 성공적으로 접수했습니다. 분석이 완료되면 알려드릴게요!",
            status_code=status.HTTP_202_ACCEPTED,
            result={
                "attemptId": main_attempt.pk,
                "status": "PENDING"
            }
        )
