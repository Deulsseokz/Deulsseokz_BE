import requests
import logging
import re
from rest_framework.views import APIView
from rest_framework import status
from .models import User, Challenge, ChallengeAttempt, ChallengeAttemptUser
from .serializers import ChallengeResponseSerializer, ChallengeAttemptSerializer
from .query_serializers import ChallengeQuerySerializer
from utils.response_wrapper import api_response
logger = logging.getLogger(__name__)

# 챌린지 정보 조회
class ChallengeInfoView(APIView):
    def get(self, request):
        query_serializer = ChallengeQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)

        place_name = query_serializer.validated_data['place']

        try:
            challenge = Challenge.objects.select_related('placeId').get(placeId__placeName=place_name)
        except Challenge.DoesNotExist:
            return api_response(
                code="CHALLENGE_NOT_FOUND",
                message="해당 장소에 대한 챌린지 정보가 없습니다.",
                status_code=status.HTTP_404_NOT_FOUND,
                is_success=False
            )
        response_serializer = ChallengeResponseSerializer(challenge)
        return api_response(result=response_serializer.data)
    
# 장소-챌린지 조건 추출
def extract_conditions(*conditions):
    extracted = [ ]
    for cond in conditions:
        if cond:
            matches = re.findall(r'\[(.*?)\]', cond)
            extracted.extend(matches)
    return extracted

# 챌린지 도전
class ChallengeAttempt(APIView):
    def post(self, request):
        place = request.data.get('place')
        friends = request.data.get('friends')
        attemptDate = request.data.get('attemptDate')
        attemptImage = request.FILES.get('attemptImage')  # 파일은 FILES에서 가져옴!

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
        fastapi_url = "http://127.0.0.1:8000/analyze/pose"
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
        fastapi_location_url = "http://127.0.0.1:8000/analyze/location"
        location_payload = {
            'candidates': place  # place가 string이라면 list로 감싸줍니다.
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
        pose_result = pose_result.get("pose", "")
        location_result = location_result.get("location", "")
        required_conditions = extract_conditions(
            challenge.condition1, challenge.condition2 # , challenge.condition3
        )

        is_success = True
        for cond in required_conditions:
            if cond not in pose_result and cond not in location_result:
                logger.warning(f"[CONDITION FAIL] '{cond}'이 pose/location 결과에 없음")
                is_success = False
                break

        # DB 저장
        # 1. ChallengeAttempt
        attempt_instance = ChallengeAttempt.objects.create(
            challengeId= challenge, # 장소에서 연결
            userId= User.objects.get(id=1), # 유저 기본 설정(request.user)
            attemptDate= attemptDate,
            attemptImage= request.build_absolute_url(attemptImage.url),
            resultComment= None, # 추후 수정
            attemptResult = is_success
        )
        serializer = ChallengeAttemptSerializer(attempt_instance)

        #2. ChallengeAttemptUser 
        friends_ids = friends if friends else [ ]
        for friend_id in friends_ids:
            # try:
            #     friend_user = User.objects.get(id=friend_id)
            #     ChallengeAttemptUser.obejcts.create(
            #         challengeAttemptId=attempt_instance,
            #         userId=friend_user
            #     )
            # except User.DoesNotExist:
            #     logger.warning(f"[WARNING] 친구 ID {friend_id}에 해당하는 유저 존재하지 않습니다.")

            # 토큰 적용 전 예외 처리 제외
            friend_user = User.objects.get(id=friend_id)
            ChallengeAttemptUser.obejcts.create(
                challengeAttemptId=attempt_instance,
                userId=friend_user
            )

        # 응답 반환
        return api_response(
            # result={
            #     "pose_analysis": analysis_result,
            #     "location_prediction": location_result
            # }
            result={
                "attemptResult": is_success,
                # "resultComment": "text",
                "attempt": 
            }
        )
