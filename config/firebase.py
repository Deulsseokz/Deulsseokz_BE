import firebase_admin
import logging
from firebase_admin import credentials, messaging
logger = logging.getLogger(__name__)

# 1. Firebase Admin SDK 초기화
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(".secrets/firebase-secret-key.json") 
        
        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK가 성공적으로 초기화되었습니다.")

except Exception as e:
    logger.info(f"Firebase Admin SDK 초기화 실패: {e}")


# 2. 알림을 보내는 함수
def send_fcm_notification(token: str, title: str, body: str, data: dict = None):
    """
    FCM 푸시 알림을 단일 기기로 보냅니다.

    :param token: 메시지를 받을 기기의 FCM 등록 토큰
    :param title: 알림의 제목
    :param body: 알림의 본문
    :param data: 알림과 함께 보낼 추가 데이터 (key-value 쌍)
    :return: 메시지 전송 성공 시 True, 실패 시 False
    """
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            token=token,
            data=data or {}
        )

        # 메시지 전송
        response = messaging.send(message)
        logger.info('Successfully sent message:', response)
        return True
    except Exception as e:
        logger.info(f'Error sending FCM message: {e}')
        return False