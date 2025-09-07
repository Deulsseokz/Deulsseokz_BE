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

<<<<<<< HEAD
        # 친구 목록 리스트 파싱
        friends_raw = request.data.get('friends', '[]')  # "[2,3]" 형태로 변경
        try:
            friends = json.loads(friends_raw)
            if not isinstance(friends, list):
                raise ValueError("friends must be a list")
        except (json.JSONDecodeError, ValueError):
            return api_response(
                {"error": "Invalid format for friends (must be JSON list string)"},
                status=400
            )
=======
        serializer = ChallengeAttemptRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
>>>>>>> 2b08ec526b3d2908b321b878b150eb40eb102b53
        
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
<<<<<<< HEAD
        # 도전 사진 S3 업로드
        if is_success:
            attemptImage.seek(0)
            image_content = attemptImage.read()  # bytes
            image_file = ContentFile(image_content)
            image_file.name = attemptImage.name  # 파일명 유지
            attempt_instance.attemptImage.save(image_file.name, image_file, save=True)
            serializer = ChallengeAttemptSerializer(attempt_instance)

            print("[DEBUG] image_file name:", image_file.name)
            print("[DEBUG] instance path:", attempt_instance.attemptImage.name)
            print("[DEBUG] S3 URL:", attempt_instance.attemptImage.url)
=======

        # Celery Task 호출 시, 메인 시도 ID와 함께 친구 ID 리스트를 전달
        process_challenge_attempt.delay(main_attempt.pk, friend_ids)
>>>>>>> 2b08ec526b3d2908b321b878b150eb40eb102b53

        logger.info(f"챌린지 시도 ID {main_attempt.pk} (친구 {len(friend_ids)}명 포함)가 큐에 추가됨.")

<<<<<<< HEAD
            # 토큰 적용 전 예외 처리 제외
            friend_user = User.objects.get(userId=friend_id)
            ChallengeAttemptUser.objects.create(
                challengeAttemptId=attempt_instance,
                userId=friend_user
            )

        # 도전 사진 앨범에 업로드 (앨범 없으면 새로 생성)
        if is_success:
            try:
                user = User.objects.get(userId=1)  # 추후 수정
                place = challenge.placeId

                # 앨범 없으면 생성
                album, created = Album.objects.get_or_create(
                    userId=user,
                    placeId=place,
                    defaults={
                        'albumName': place.placeName
                    }
                )

                if created:
                    logger.info(f"[ALBUM CREATED] userId={user.userId}, place={place.placeName}")

            except Exception as e:
                logger.warning(f"[ALBUM ERROR] 앨범 생성 또는 조회 중 오류 발생: {str(e)}")
            else:
                # 이미지 파일 재사용 위해 다시 포인터 초기화
                attemptImage.seek(0)
                photo_image = ContentFile(attemptImage.read())
                photo_image.name = attemptImage.name

                # Photo 생성
                photo = Photo.objects.create(
                    album=album,
                    photoUrl=photo_image,
                    photoContent="챌린지 인증 사진",
                    date=attemptDate
                )

                logger.info(f"[PHOTO ADDED TO ALBUM] photoId={photo.photoId}, albumId={album.albumId}, path={photo.photoUrl.name}")

        # 유저 도전 횟수 카운트
        attempt_count = ChallengeAttempt.objects.filter(
            userId = User.objects.get(userId=1), # 유저 기본 설정(request.user)
            challengeId__placeId = challenge.placeId
        ).count()

        # 이번 도전은 몇 번째인지 (기존 도전 수 + 1)
        current_attempt = attempt_count + 1

        # 조건1: location과 일치 여부
        condition1_pass = any(cond in location_result for cond in required_conditions)

        # 조건2: pose와 일치 여부
        condition2_pass = any(cond in pose_result_str for cond in required_conditions)

        # 최종 성공 여부: 둘 다 만족해야 True
        is_success = condition1_pass and condition2_pass

        # 응답 반환
=======
        # 사용자에게는 즉시 응답을 보냄
>>>>>>> 2b08ec526b3d2908b321b878b150eb40eb102b53
        return api_response(
            code="CHALLENGE_SUBMITTED",
            message="챌린지 사진을 성공적으로 접수했습니다. 분석이 완료되면 알려드릴게요!",
            status_code=status.HTTP_202_ACCEPTED,
            result={
                "attemptId": main_attempt.pk,
                "status": "PENDING"
            }
        )
