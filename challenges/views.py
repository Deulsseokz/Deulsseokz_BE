import requests
import logging
import re
import json
from rest_framework.views import APIView
from rest_framework import status
from .models import User, Challenge, ChallengeAttempt, ChallengeAttemptUser
from places.models import FavoritePlace
from .serializers import ChallengeResponseSerializer, ChallengeAttemptSerializer
from .query_serializers import ChallengeQuerySerializer
from utils.response_wrapper import api_response
logger = logging.getLogger(__name__)

# 전체 챌린지 목록 조회
class ChallengeListView(APIView):
    def get(self, request):
        try: 
            user = User.objects.get(userId=1)
        except User.DoesNotExist:
            return api_response(
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        result = []
        challenges = Challenge.objects.all()

        for challenge in challenges:
            # 해당 유저의 성공한 도전 이력이 있는지 확인
            attempt = ChallengeAttempt.objects.filter(
                userId=user,
                challengeId=challenge,
                attemptResult=True
            ).order_by('-attemptDate').first()

            result.append({
                "challengeId": challenge.challengeId,
                "place": challenge.placeId.placeName,
                "isChallenged": attempt is not None,
                "challengePhoto": attempt.attemptImage if attempt else None,
                "location": challenge.placeId.location
            })

        return api_response(
            result=result
        )

# 챌린지 정보 조회
class ChallengeInfoView(APIView):
    def get(self, request):
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

        user = User.objects.get(userId=1)

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
                FavoritePlace.objects.filter(userId=user).values_list('placeId', flat=True)
            )

            result = []
            for challenge in challenges:
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
                FavoritePlace.objects.filter(userId=user).values_list('placeId', flat=True)
            )

            result = []
            for challenge in challenges:
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
class ChallengeAttemptView(APIView):
    def post(self, request):
        place = request.data.get('place')
        friends_list = request.data.get('friends', []) # 리스트 형식 지정
        attemptDate = request.data.get('attemptDate')
        attemptImage = request.FILES.get('attemptImage')  # 파일은 FILES에서 가져옴!

        # 친구 목록 리스트 파싱
        try:
            friends = json.loads(friends_list)
        except json.JSONDecodeError:
            return api_response({"error": "Invalid format for friends"}, status=400)

        if not all([place, attemptDate, attemptImage]):
            return api_response(
                code="INVALID_INPUT",
                message="place, attemptDate, attemptImage는 필수입니다.",
                status_code=status.HTTP_400_BAD_REQUEST,
                is_success=False
            )
        
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
        fastapi_url = "http://localhost:8001/ai/analyze/pose"
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
        fastapi_location_url = "http://localhost:8001/ai/analyze/location"
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
        pose_result_data = pose_result.get("results", [ ])
        pose_result_str = " "
        if pose_result_data and isinstance(pose_result_data, list):
            pose_result_str = pose_result_data[0].get("pose", "")

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

        # DB 저장
        # 1. ChallengeAttempt
        attempt_instance = ChallengeAttempt.objects.create(
            challengeId= challenge, # 장소에서 연결
            userId= User.objects.get(userId=1), # 유저 기본 설정(request.user)
            attemptDate= attemptDate,
            # attemptImage= request.build_absolute_url(attemptImage.url),
            attemptImage = attemptImage,
            resultComment= None, # 추후 수정
            attemptResult = is_success
        )
        serializer = ChallengeAttemptSerializer(attempt_instance)

        #2. ChallengeAttemptUser 
        friends_ids = friends if friends else [ ]
        for friend_id in friends_ids:
            # try:
            #     friend_user = User.objects.get(id=friend_id)
            #     ChallengeAttemptUser.objects.create(
            #         challengeAttemptId=attempt_instance,
            #         userId=friend_user
            #     )
            # except User.DoesNotExist:
            #     logger.warning(f"[WARNING] 친구 ID {friend_id}에 해당하는 유저 존재하지 않습니다.")

            # 토큰 적용 전 예외 처리 제외
            friend_user = User.objects.get(userId=friend_id)
            ChallengeAttemptUser.objects.create(
                challengeAttemptId=attempt_instance,
                userId=friend_user
            )

        # 유저 도전 횟수 카운트
        attempt_count = ChallengeAttempt.objects.filter(
            userId = User.objects.get(userId=1), # 유저 기본 설정(request.user)
            challengeId__placeId = challenge.placeId
        ).count()

        # 이번 도전은 몇 번째인지 (기존 도전 수 + 1)
        current_attempt = attempt_count + 1

        # 응답 반환
        return api_response(
            # result={
            #     "pose_analysis": analysis_result,
            #     "location_prediction": location_result
            # }
            result={
                "attemptResult": is_success,
                # "resultComment": "text",
                "attempt": current_attempt
            }
        )
