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

        # 2) auth 유저 조회/생성
        email = payload.get("email")
        username_seed = email or payload.get("sub")

        with transaction.atomic():
            auth_user, created = AuthUser.objects.get_or_create(
                email=email,
                defaults={"username": _build_unique_username(username_seed)},
            )

            # 3) 신규라면 앱 유저(users.User)도 한 줄 생성
            app_user_id = None
            if created:
                app_user = AppUser.objects.create(
                    userName=payload.get("name") or auth_user.username,
                    profileImage=payload.get("picture"),
                    # representBadge는 처음엔 None
                )
                app_user_id = app_user.userId

        # 4) 자체 토큰 + isNew 포함해 반환
        refresh = RefreshToken.for_user(auth_user)
        body = {
            "ok": True,
            "isNew": created,  # 새 유저면 True, 기존이면 False
            # "user": {
            #     "email": auth_user.email,
            #     "username": getattr(auth_user, "username", None),
            #     "userId": app_user_id,
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