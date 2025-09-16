import requests
import logging
from celery import shared_task
from django.core.files.base import ContentFile
from django.db import transaction
from config.firebase import send_fcm_notification

from .models import User, Challenge, ChallengeAttempt, ChallengeAttemptUser
from albums.models import Album, Photo
from .utils import extract_conditions

logger = logging.getLogger(__name__)

@shared_task
def process_challenge_attempt(main_attempt_id, friend_ids):
    try:
        # 1. 메인 시도(요청자)의 레코드를 가져옴
        main_attempt = ChallengeAttempt.objects.select_related('challengeId', 'userId').get(pk=main_attempt_id)
        challenge = main_attempt.challengeId
        requester = main_attempt.userId # 요청자
        
        main_attempt.status = ChallengeAttempt.AttemptStatus.PROCESSING
        main_attempt.save()

        # 2. FastAPI 분석 호출 (기존과 동일)
        # ... 포즈 분석 및 장소 분석 코드 ...
        final_success = True # 임시로 성공으로 가정

        # 3. 모든 참여자 User 객체 수집
        participant_users = [requester]
        if friend_ids:
            valid_friends = User.objects.filter(userId__in=friend_ids)
            participant_users.extend(list(valid_friends))

        # 4. 원본 로직을 그대로 복원한 DB 저장 트랜잭션
        with transaction.atomic():
            # 이미지 바이트를 한 번만 읽어 재사용
            main_attempt.attemptImage.seek(0)
            image_bytes = main_attempt.attemptImage.read()
            image_name = main_attempt.attemptImage.name

            created_attempts = {} # {user_obj: attempt_instance} 맵

            # 4-1. 각 참여자별로 ChallengeAttempt, Album, Photo 레코드를 생성
            for user_obj in participant_users:
                attempt_instance = None
                if user_obj.userId == requester.userId:
                    # 요청자는 기존 레코드를 업데이트
                    main_attempt.attemptResult = final_success
                    main_attempt.status = ChallengeAttempt.AttemptStatus.SUCCESS
                    main_attempt.save()
                    attempt_instance = main_attempt
                else:
                    # 친구들은 새로운 레코드를 생성
                    attempt_instance = ChallengeAttempt.objects.create(
                        challengeId=challenge,
                        userId=user_obj,
                        attemptDate=main_attempt.attemptDate,
                        attemptResult=final_success,
                        status=ChallengeAttempt.AttemptStatus.SUCCESS
                    )
                    # 친구의 attempt 레코드에도 이미지 파일을 저장
                    img_file = ContentFile(image_bytes, name=image_name)
                    attempt_instance.attemptImage.save(img_file.name, img_file, save=True)

                created_attempts[user_obj] = attempt_instance

                # 각자의 앨범에 사진을 추가
                album, _ = Album.objects.get_or_create(
                    userId=user_obj,
                    placeId=challenge.placeId
                )
                Photo.objects.create(
                    album=album,
                    photoUrl=attempt_instance.attemptImage,
                    date=attempt_instance.attemptDate,
                    challengeAttemptId=attempt_instance
                )

            # 4-2. 각자의 ChallengeAttempt 레코드에 '함께 도전한 모든 사람' 정보를 연결
            for owner_obj, attempt_instance in created_attempts.items():
                for participant_obj in participant_users:
                    ChallengeAttemptUser.objects.create(
                        challengeAttemptId=attempt_instance,
                        userId=participant_obj
                    )
        
        logger.info(f"챌린지 시도 ID {main_attempt_id}와 연결된 모든 참여자 처리 완료.")

        # 결과 알림 발송
        place_name = challenge.placeId.placeName
        title = "챌린지 성공! 🎉" if final_success else "챌린지 실패 😢"
        body = f"'{place_name}' 챌린지 결과가 도착했어요. 확인해보세요!"

        for user in participant_users:
            if user.fcm_token:
                # 각자의 attemptId를 데이터 페이로드에 담아 보냄 (모든 챌린지 참여자에게 보냄)
                user_attempt_id = created_attempts[user].pk
                data = {"attemptId": str(user_attempt_id), "type": "challenge_result"}
                send_fcm_notification(user.fcm_token, title, body, data)

    except Exception as e:
        logger.error(f"챌린지 시도 ID {main_attempt_id} 처리 중 에러: {e}")
        if 'main_attempt' in locals():
            main_attempt.status = ChallengeAttempt.AttemptStatus.FAILED
            main_attempt.resultComment = str(e)
            main_attempt.save()

            # 결과 알림 발송 
            requester = main_attempt.userId
            if requester.fcm_token:
                title = "챌린지 처리 실패"
                body = f"'{main_attempt.challengeId.placeId.placeName}' 챌린지 분석 중 오류가 발생했어요."
                data = {"attemptId": str(main_attempt_id), "type": "challenge_result"}
                send_fcm_notification(requester.fcm_token, title, body, data)