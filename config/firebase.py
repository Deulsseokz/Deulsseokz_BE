import firebase_admin
from firebase_admin import credentials, messaging

# 1. Firebase Admin SDK 초기화
try:
    if not firebase_admin._apps:
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)
except Exception as e:
    print(f"Firebase Admin SDK 초기화 실패: {e}")


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
        print('Successfully sent message:', response)
        return True
    except Exception as e:
        print(f'Error sending FCM message: {e}')
        return False