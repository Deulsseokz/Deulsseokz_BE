import requests
import logging
from celery import shared_task
from django.core.files.base import ContentFile
from django.db import transaction

from .models import User, Challenge, ChallengeAttempt, ChallengeAttemptUser
from albums.models import Album, Photo
from .views import extract_conditions # 챌린지 조건 추출 함수 import

logger = logging.getLogger(__name__)

@shared_task
def process_challenge_attempt(attempt_id):
    """
    챌린지 시도를 백그라운드에서 처리하는 Celery 태스크.
    시간이 오래 걸리는 모든 작업을 여기서 수행합니다.
    """
    try:
        # 1. ID를 기반으로 DB에서 필요한 객체들을 가져옴
        attempt = ChallengeAttempt.objects.select_related('challengeId', 'userId').get(pk=attempt_id)
        challenge = attempt.challengeId
        app_user = attempt.userId
        
        # 함께 도전한 친구 목록 가져오기
        # 여기서는 설명을 위해 요청자만 처리하는 것으로 단순화합니다.
        # 친구 로직은 ChallengeAttemptUser 모델을 통해 나중에 연결할 수 있습니다.

        # 2. 상태를 '처리중'으로 업데이트
        attempt.status = ChallengeAttempt.AttemptStatus.PROCESSING
        attempt.save()

        # 3. FastAPI 호출 (포즈 분석)
        fastapi_pose_url = "http://13.125.101.75:8001/analyze/pose"
        files_pose = {'file': attempt.attemptImage.file}
        pose_response = requests.post(fastapi_pose_url, files=files_pose)
        pose_response.raise_for_status()
        pose_result = pose_response.json()
        pose_result_str = pose_result.get("pose", "").lower()
        logger.info(f"[비동기 포즈 분석 결과] {pose_result_str}")

        # 4. FastAPI 호출 (장소 분석)
        fastapi_loc_url = "http://13.125.101.75:8001/analyze/location"
        location_payload = {'candidates': challenge.placeId.placeName}
        attempt.attemptImage.seek(0) # 파일 포인터 초기화
        files_loc = {'file': attempt.attemptImage.file}
        location_response = requests.post(fastapi_loc_url, files=files_loc, data=location_payload)
        location_response.raise_for_status()
        location_result = location_response.json()
        location_result_str = location_result.get("location", "").lower()
        logger.info(f"[비동기 장소 분석 결과] {location_result_str}")

        # 5. 챌린지 성공 여부 판별
        required_conditions = [cond.lower() for cond in extract_conditions(challenge.condition1, challenge.condition2)]
        final_success = all(any(cond in res for res in [pose_result_str, location_result_str]) for cond in required_conditions)

        # 6. 최종 결과 DB에 업데이트
        with transaction.atomic():
            attempt.attemptResult = final_success
            attempt.status = ChallengeAttempt.AttemptStatus.SUCCESS
            attempt.save()

            # 성공했다면 앨범에도 사진 추가
            if final_success:
                album, _ = Album.objects.get_or_create(
                    userId=app_user,
                    placeId=challenge.placeId
                )
                Photo.objects.create(
                    album=album,
                    photoUrl=attempt.attemptImage,
                    date=attempt.attemptDate,
                    challengeAttemptId=attempt
                )
        
        logger.info(f"챌린지 시도 ID {attempt_id} 처리가 성공적으로 완료되었습니다.")
        # 추후 웹소켓이나 푸시 알림으로 사용자에게 성공/실패를 알리는 로직 여기에

    except Exception as e:
        logger.error(f"챌린지 시도 ID {attempt_id} 처리 중 에러 발생: {e}")
        if 'attempt' in locals():
            attempt.status = ChallengeAttempt.AttemptStatus.FAILED
            attempt.resultComment = str(e) # 에러 메시지 저장
            attempt.save()