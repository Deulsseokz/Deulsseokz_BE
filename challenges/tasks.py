import requests
import logging
import json
import mimetypes
from celery import shared_task
from django.core.files.base import ContentFile
from django.conf import settings
from django.db import transaction
from config.firebase import send_fcm_notification

from .models import User, Challenge, ChallengeAttempt, ChallengeAttemptUser
from albums.models import Album, Photo
from .utils import extract_conditions

logger = logging.getLogger(__name__)

@shared_task
def process_challenge_attempt(main_attempt_id, friend_ids):
    main_attempt = None # 에러 발생 시 참조를 위해 미리 선언
    try:
        # 1. 메인 시도(요청자)의 레코드를 가져옴
        main_attempt = ChallengeAttempt.objects.select_related('challengeId', 'userId', 'challengeId__placeId').get(pk=main_attempt_id)
        challenge = main_attempt.challengeId
        requester = main_attempt.userId
        
        main_attempt.status = ChallengeAttempt.AttemptStatus.PROCESSING
        main_attempt.save()

        # 2. FastAPI 분석 호출
        final_success = False
        result_comment = ""
        analysis_result = {} # AI 응답 전체를 저장할 변수

        try:
            api_url = settings.FASTAPI_ANALYSIS_URL

            main_attempt.attemptImage.seek(0)
            image_file_bytes = main_attempt.attemptImage.read()
            
            image_name = main_attempt.attemptImage.name
            content_type, _ = mimetypes.guess_type(image_name)
            if content_type is None:
                content_type = 'application/octet-stream' # 타입을 알 수 없을 때의 기본값

            files = {'image': (image_name, image_file_bytes, content_type)}
            
            # utils 함수를 통해 키워드 리스트 추출
            condition_keywords = extract_conditions(challenge)
            data = {
                'conditions': json.dumps(condition_keywords),
                'place_name': challenge.placeId.placeName
            } 

            # DEBUG: AI 서버로 보내기 직전의 데이터 확인
            print("\n" + "="*50)
            print("[DEBUG] Data to send to AI Server:")
            print(f"URL: {api_url}")
            print(f"Image exists: {image_file_bytes is not None and len(image_file_bytes) > 0}")
            print(f"Conditions: {data.get('conditions')}")
            print(f"Place Name: {data.get('place_name')}")
            print("="*50 + "\n")

            response = requests.post(api_url, files=files, data=data, timeout=60)
            response.raise_for_status()

            analysis_result = response.json()
            final_success = analysis_result.get('success', False)
            result_comment = analysis_result.get('message', 'AI 서버로부터 메시지가 없습니다.')

            # DEBUG: AI 서버로부터 받은 응답 확인
            print("\n" + "="*50)
            print("[DEBUG] Response from AI Server:")
            print(f"Status Code: {response.status_code}")
            print(f"Response Body: {analysis_result}")
            print("="*50 + "\n")

            logger.info(f"AI 분석 결과 수신 (시도 ID: {main_attempt_id}): {analysis_result}")

        except requests.RequestException as e:
            result_comment = f"AI 서버와 통신 중 오류가 발생했습니다: {e}"
            logger.error(f"AI 서버 통신 오류 (시도 ID: {main_attempt_id}): {e}")
            raise 

        # 3. 모든 참여자 User 객체 수집
        participant_users = [requester]
        if friend_ids:
            valid_friends = User.objects.filter(userId__in=friend_ids)
            participant_users.extend(list(valid_friends))

        # 4. DB 저장 트랜잭션
        with transaction.atomic():
            main_attempt.attemptImage.seek(0)
            image_bytes = main_attempt.attemptImage.read()
            image_name = main_attempt.attemptImage.name

            created_attempts = {}

            # AI가 보낸 상세 결과(details)를 추출
            result_details_data = analysis_result.get('details', {})

            # 4-1. 각 참여자별로 레코드 생성/업데이트
            for user_obj in participant_users:
                attempt_instance = None
                attempt_status = ChallengeAttempt.AttemptStatus.SUCCESS if final_success else ChallengeAttempt.AttemptStatus.FAILED

                if user_obj.userId == requester.userId:
                    # 요청자는 기존 레코드 업데이트
                    main_attempt.attemptResult = final_success
                    main_attempt.status = attempt_status
                    main_attempt.resultComment = result_comment
                    main_attempt.result_details = result_details_data 
                    main_attempt.save()
                    attempt_instance = main_attempt
                else:
                    # 친구들은 새로운 레코드 생성
                    attempt_instance = ChallengeAttempt.objects.create(
                        challengeId=challenge,
                        userId=user_obj,
                        attemptDate=main_attempt.attemptDate,
                        attemptResult=final_success,
                        status=attempt_status,
                        resultComment=result_comment,
                        result_details=result_details_data
                    )
                    img_file = ContentFile(image_bytes, name=image_name)
                    attempt_instance.attemptImage.save(img_file.name, img_file, save=True)

                created_attempts[user_obj] = attempt_instance

                # 각자의 앨범에 사진 추가 (성공했을 경우에만)
                if final_success:
                    album, _ = Album.objects.get_or_create(userId=user_obj, placeId=challenge.placeId)
                    Photo.objects.create(
                        album=album,
                        photoUrl=attempt_instance.attemptImage,
                        date=attempt_instance.attemptDate,
                        challengeAttemptId=attempt_instance
                    )

            # 4-2. 함께 도전한 사람 정보 연결
            for owner_obj, attempt_instance in created_attempts.items():
                for participant_obj in participant_users:
                    ChallengeAttemptUser.objects.create(
                        challengeAttemptId=attempt_instance,
                        userId=participant_obj
                    )
        
        logger.info(f"챌린지 시도 ID {main_attempt_id}와 연결된 모든 참여자 처리 완료.")

        # 5. 결과 알림 발송
        place_name = challenge.placeId.placeName
        title = "챌린지 성공! 🎉" if final_success else "챌린지 실패 😢"
        body = f"'{place_name}' 챌린지 결과가 도착했어요. 확인해보세요!"

        for user in participant_users:
            if user.fcm_token:
                user_attempt_id = created_attempts[user].pk
                data = {"attemptId": str(user_attempt_id), "type": "challenge_result"}
                send_fcm_notification(user.fcm_token, title, body, data)
                logger.info(f"FCM 알림 발송 : userId={user.userId}, attemptId={user_attempt_id}, title='{title}'")

    except Exception as e:
        logger.error(f"챌린지 시도 ID {main_attempt_id} 처리 중 에러: {e}")
        if main_attempt: # main_attempt가 할당된 후에만 실행되도록 수정
            main_attempt.status = ChallengeAttempt.AttemptStatus.FAILED
            main_attempt.resultComment = main_attempt.resultComment or str(e)
            main_attempt.save()

            # 결과 알림 발송 
            requester = main_attempt.userId
            if requester.fcm_token:
                title = "챌린지 처리 실패"
                body = f"'{main_attempt.challengeId.placeId.placeName}' 챌린지 분석 중 오류가 발생했어요."
                data = {"attemptId": str(main_attempt_id), "type": "challenge_result"}
                send_fcm_notification(requester.fcm_token, title, body, data)
                logger.info(f"FCM 알림 발송 실패: userId={user.userId}, attemptId={user_attempt_id}, title='{title}'")