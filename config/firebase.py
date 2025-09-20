import firebase_admin
import logging
from firebase_admin import credentials, messaging
from django.conf import settings 

logger = logging.getLogger(__name__)

# 진단용 프린트 문을 추가하여 이 파일이 로드되는 시점을 명확히 확인합니다.
print("\n" + "!"*20 + " >> config/firebase.py 모듈 로딩 시작 << " + "!"*20 + "\n")

# ===================================================================
# 1. Firebase Admin SDK 초기화
# ===================================================================
try:
    # 이미 초기화되었는지 확인하여 중복 실행을 방지합니다.
    if not firebase_admin._apps:
        # settings.py에 설정된 절대 경로를 사용합니다.
        cred = credentials.Certificate(settings.FIREBASE_SECRET_KEY_PATH)
        
        firebase_admin.initialize_app(cred)
        # 시작 로그에서 쉽게 확인할 수 있도록 print 문을 사용합니다.
        print("✅ Firebase Admin SDK가 성공적으로 초기화되었습니다.")

except Exception as e:
    # 초기화 실패 시, 정확한 원인을 파악하기 위해 상세 에러를 로그에 남깁니다.
    logger.error("🔥 Firebase Admin SDK 초기화 실패: %s", e, exc_info=True)
    print(f"🔥 Firebase Admin SDK 초기화 실패: {e}")
# ===================================================================


# ===================================================================
# 2. 알림 전송 함수
# ===================================================================
def send_fcm_notification(token: str, title: str, body: str, data: dict = None):
    """
    FCM 푸시 알림을 단일 기기로 보냅니다.
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

        response = messaging.send(message)
        logger.info('Successfully sent message: %s', response)
        return True
    except Exception as e:
        logger.error('Error sending FCM message: %s', e, exc_info=True)
        return False