from django.conf import settings
from django.db import transaction
from django.utils.text import slugify
import secrets

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from django.contrib.auth import get_user_model

from users.models import User as AppUser  # 별칭 지정

AuthUser = get_user_model()

def _tokens_payload(refresh: RefreshToken):
    access = refresh.access_token
    return {
        "access": str(access),
        "refresh": str(refresh),
        "access_expires": int(access["exp"]),
        "refresh_expires": int(refresh["exp"]),
    }

# 중복 방지
def _build_unique_username(seed: str | None) -> str:
    base = slugify((seed or "").split("@")[0]) or "user"
    candidate = base
    for _ in range(5):
        if not AuthUser.objects.filter(username=candidate).exists():
            return candidate
        candidate = f"{base}-{secrets.randbelow(10000):04d}"
    return f"{base}-{secrets.token_hex(3)}"

@method_decorator(csrf_exempt, name="dispatch")
class GoogleIdTokenLogin(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        id_token_str = request.data.get("idToken")
        if not id_token_str:
            return Response({"detail": "idToken required"}, status=400)

        # 1) 구글 idToken 검증
        try:
            payload = google_id_token.verify_oauth2_token(
                id_token_str, google_requests.Request(), settings.GOOGLE_CLIENT_ID
            )
            if payload.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
                raise ValueError("Bad issuer")
        except Exception:
            return Response({"detail": "Invalid Google idToken"}, status=401)

        email = payload.get("email")
        username_seed = email or payload.get("sub")

        with transaction.atomic():
            # 2) 인증 유저 upsert
            auth_user, created_auth = AuthUser.objects.get_or_create(
                email=email,
                defaults={"username": _build_unique_username(username_seed)},
            )

            # 3) 앱 유저 1:1 보장
            #    - 우선 authUser로 직접 조회
            app_user = AppUser.objects.filter(authUser=auth_user).first()

            if not app_user:
                # 같은 사람의 기존 row가 있을 수 있으니(예: 선행 가입) 한 번 더 안전하게 탐색
                # 기준이 없다면 새로 만든다 (userName, profileImage만 초기 세팅)
                app_user = AppUser.objects.create(
                    authUser=auth_user,  # ★ 핵심: 연결
                    userName=payload.get("name") or getattr(auth_user, "username", None),
                    profileImage=payload.get("picture"),
                )

        # 4) 토큰 발급
        refresh = RefreshToken.for_user(auth_user)
        body = {
            "ok": True,
            "isNew": created_auth,  # 인증 유저 기준
            # "user": {
            #     "userId": app_user.userId,
            #     "userName": app_user.userName,
            #     "profileImage": app_user.profileImage,
            # },
        }
        body.update(_tokens_payload(refresh))
        return Response(body, status=200)

class RotateTokenView(APIView):
    """리프레시 토큰으로 재발급"""
    permission_classes = [AllowAny]

    def post(self, request):
        raw = request.data.get("refresh")  # ← 바디로 받음
        if not raw:
            return Response({"detail": "refresh required"}, status=400)
        try:
            old = RefreshToken(raw)
            new = old.rotate()
        except TokenError:
            return Response({"detail": "invalid refresh"}, status=401)

        return Response(_tokens_payload(new), status=200)