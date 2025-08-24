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
    
# 장소-챌린지 조건 추출
def extract_conditions(*conditions):
    extracted = []
    for cond in conditions:
        matches = re.findall(r'\[(.*?)\]', cond)
        extracted.extend(matches)
    return extracted

# 챌린지 도전
class ChallengeAttemptView(AuthedAPIView):
    @swagger_auto_schema(request_body=ChallengeAttemptRequestSerializer)
    def post(self, request):
        app_user = self.get_app_user(request)

        place = request.data.get('place')
        friends_list = request.data.get('friends', []) # 리스트 형식 지정
        attemptDate = request.data.get('attemptDate')
        attemptImage = request.FILES.get('attemptImage')  # 파일은 FILES에서 가져옴!

        # 친구 목록 리스트 파싱
        friends_raw = request.data.get('friends', [])
        if isinstance(friends_raw, str):
            friends = json.loads(friends_raw)
        elif isinstance(friends_raw, list):
            friends = friends_raw
        else:
            friends = []
            
        # 장소에 속한 챌린지 가져오기
        try:
            challenge = Challenge.objects.select_related('placeId').get(placeId__placeName = place)
        except Challenge.DoesNotExist:
            return api_response(
                code="CHALLENGE_NOT_FOUND",
                message=f"장소 '{place}'에 해당하는 챌린지가 없습니다.",
                status_code=status.HTTP_404_NOT_FOUND,
                is_success=False
            )

        # === FastAPI 호출 (포즈 분석) ===
        fastapi_url = "http://13.125.101.75:8001/analyze/pose"
        files = {
            'file': (attemptImage.name, attemptImage.read(), attemptImage.content_type)
        }

        try:
            response = requests.post(fastapi_url, files=files)
            response.raise_for_status()
            pose_result = response.json()
        except requests.exceptions.RequestException as e:
            return api_response(
                code="POSE_ANALYSIS_FAILED",
                message="포즈 분석 실패",
                status_code=status.HTTP_502_BAD_GATEWAY,
                is_success=False,
                result={"error": str(e)}
            )
        
        logger.info(f"[POSE ANALYSIS RESULT] {pose_result}")

        # 해당하는 장소의 조건 중 장소에 관련된 것과 포즈 분석한 결과를 비교 
        # 조건 중에 find 함수 사용해 특정 단어 포함되어 있는 지 확인 해 추출 

        # === (장소 판별 호출) ===
        fastapi_location_url = "http://13.125.101.75:8001/analyze/location"
        location_payload = {
            'candidates': place  # place가 string이라면 list로 감싸기
        }

        # attemptImage는 .read() 했기 때문에 다시 읽어야 함
        attemptImage.seek(0) # 다시 읽도록 포인터 초기화
        files['file'] = (attemptImage.name, attemptImage.read(), attemptImage.content_type)

        try:
            location_response = requests.post(fastapi_location_url, files=files, data=location_payload)
            location_response.raise_for_status()
            location_result = location_response.json()
        except requests.exceptions.RequestException as e:
            return api_response(
                code="LOCATION_ANALYSIS_FAILED",
                message="장소 판별 실패",
                status_code=status.HTTP_502_BAD_GATEWAY,
                is_success=False,
                result={"error": str(e)}
            )
                
        logger.info(f"[LOCATION ANALYSIS RESULT] {location_result}")

        # 조건 추출 후 검사
        # pose_result_data = pose_result.get("results", [ ])
        # pose_result_str = " "
        # if pose_result_data and isinstance(pose_result_data, list):
        pose_result_str = pose_result.get("pose", "").lower()

        location_result = location_result.get("location", "")

        logger.debug(f"[DEBUG] pose_result: {pose_result_str} (type: {type(pose_result_str)})")
        logger.debug(f"[DEBUG] location_result: {location_result} (type: {type(location_result)})")

        # 소문자로 변환
        pose_result_str = pose_result_str.lower()
        location_result = location_result.lower()

        # condition1, condition2에서 필요한 키워드들 추출
        required_conditions = [cond.lower() for cond in extract_conditions(challenge.condition1, challenge.condition2)]

        is_success = True
        for cond in required_conditions:
            if cond not in pose_result_str and cond not in location_result:
                logger.warning(f"[CONDITION FAIL] '{cond}'이 pose/location 결과에 없음")
                is_success = False
                break

        # === DB 저장 (모두에게 개별 Attempt 생성) ===
        with transaction.atomic():
            # 0) 참여자 수집 (본인 + 친구)
            #    - friends_ids를 유효한 사용자만 필터링하여 User 객체 리스트
            participant_users = [app_user]
            valid_friend_users = []
            for friend_id in (friends if friends else []):
                try:
                    u = User.objects.get(userId=friend_id)
                    valid_friend_users.append(u)
                except User.DoesNotExist:
                    logger.warning(f"[WARNING] 친구 ID {friend_id}에 해당하는 유저 존재하지 않습니다.")
            participant_users.extend(valid_friend_users)

            # 1) 공통 업로드용 이미지 바이트 보관 (여러 Attempt에 동일 파일 저장)
            attemptImage.seek(0)
            image_bytes = attemptImage.read()
            image_name = attemptImage.name
            image_mime = attemptImage.content_type

            # 2) 결과 판정 (장소/포즈 각각 만족 여부)
            condition1_pass = any(cond in location_result for cond in required_conditions)
            condition2_pass = any(cond in pose_result_str for cond in required_conditions)
            final_success = condition1_pass and condition2_pass

            # 3) 각 참여자별로 Attempt/Photo/AttemptUser 생성
            created_attempts = {}  # {userId: attempt_instance}
            for user_obj in participant_users:
                # 3-1) ChallengeAttempt 생성
                attempt_instance = ChallengeAttempt.objects.create(
                    challengeId=challenge,
                    userId=user_obj,
                    attemptDate=attemptDate,
                    resultComment=None,
                    attemptResult=final_success
                )

                # 3-2) 도전 사진 저장 (같은 바이트를 재사용)
                img_file = ContentFile(image_bytes)  # 새 ContentFile로 래핑
                img_file.name = image_name
                attempt_instance.attemptImage.save(img_file.name, img_file, save=True)

                # 3-3) 앨범/사진 생성 (사용자별 앨범에 동일 사진 1장씩 기록)
                album, _ = Album.objects.get_or_create(
                    userId=user_obj,
                    placeId=challenge.placeId,
                    defaults={"representativePhotoId": None}
                )
                Photo.objects.create(
                    album=album,
                    photoUrl=attempt_instance.attemptImage,  # FileField 참조
                    date=attemptDate or None,
                    challengeAttemptId=attempt_instance,
                )

                created_attempts[user_obj.userId] = attempt_instance

            # 4) 각 Attempt에 모든 참여자를 ChallengeAttemptUser로 연결
            # (사진 속 함께한 사람 리스트가 동일하게 걸리도록)
            for user_obj in participant_users:
                attempt_instance = created_attempts[user_obj.userId]
                for participant in participant_users:
                    ChallengeAttemptUser.objects.create(
                        challengeAttemptId=attempt_instance,
                        userId=participant
                    )

            # 5) 응답은 "요청자(app_user)" 기준으로 몇 번째 도전인지 계산
            attempt_count_for_me = ChallengeAttempt.objects.filter(
                userId=app_user,
                challengeId__placeId=challenge.placeId
            ).count()
            current_attempt_for_me = attempt_count_for_me  # 방금 1건 생성 포함

            return api_response(
                result={
                    "attemptResult": final_success,
                    "condition1": condition1_pass,
                    "condition2": condition2_pass,
                    "attempt": current_attempt_for_me,
                    "createdAttempts": {
                        "ownerUserId": app_user.userId,
                        "friendUserIds": [u.userId for u in valid_friend_users],
                        "count": len(participant_users)
                    }
                }
            )
