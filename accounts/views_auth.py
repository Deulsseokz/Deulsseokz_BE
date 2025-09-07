import secrets
import logging
from django.conf import settings
from django.db import transaction
from django.utils.text import slugify
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.settings import api_settings
from users.models import User as AppUser
from badges.models import UserBadge, Badge

logger = logging.getLogger(__name__)

AuthUser = get_user_model()

def _build_unique_username(seed: str | None) -> str:
    base = slugify((seed or "").split("@")[0]) or "user"
    candidate = base
    for _ in range(5):
        if not AuthUser.objects.filter(username=candidate).exists():
            return candidate
        candidate = f"{base}-{secrets.randbelow(10000):04d}"
    return f"{base}-{secrets.token_hex(3)}"

def _tokens_payload(refresh: RefreshToken):
    access = refresh.access_token
    return {
        "access": str(access),
        "refresh": str(refresh),
        "access_expires": int(access["exp"]),
        "refresh_expires": int(refresh["exp"]),
    }

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

            # 3) 앱 유저 1:1 보장 (필드명: auth)
            app_user = AppUser.objects.filter(auth=auth_user).first()
            if not app_user:
                app_user = AppUser.objects.create(
                    auth=auth_user,  # 필드명 통일
                    userName=payload.get("name") or getattr(auth_user, "username", None),
                    profileImage=payload.get("picture"),
                    representBadge_Id=1, # 가입 시 첫 만남 배지 부여
                )

            # UserBadge에도 배지 1 부여
            try:
                starter_badge = Badge.objects.get(pk=1)
                UserBadge.objects.get_or_create(
                    userId=app_user,
                    badgeId=starter_badge,
                )
            except Badge.DoesNotExist:
                logger.warning("Badge(pk=1)가 존재하지 않아 UserBadge 부여를 건너뜀")

        # 4) 토큰 발급
        refresh = RefreshToken.for_user(auth_user)
        body = {
            "ok": True,
            "isNew": created_auth,
            # "user": {
            #     "userId": app_user.userId,
            #     "userName": app_user.userName,
            #     "profileImage": app_user.profileImage,
            # },
        }
        body.update(_tokens_payload(refresh))
        return Response(body, status=200)

class RotateTokenView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # request.data가 dict가 아닐 가능성 방어
        raw = request.data.get("refresh") if isinstance(request.data, dict) else None
        if not raw or not isinstance(raw, str):
            return Response({"detail": "refresh required"}, status=400)

        try:
            old = RefreshToken(raw)  # 서명/만료 검증
            if old.payload.get("token_type") != "refresh":
                return Response({"detail": "not a refresh token"}, status=401)

            user_id = old[api_settings.USER_ID_CLAIM]  # 기본 'user_id'
            user = AuthUser.objects.get(pk=user_id)

            # (옵션) 블랙리스트 사용 시 이전 refresh 폐기
            try:
                old.blacklist()  # token_blacklist 앱 및 설정이 있을 때만 동작
            except Exception:
                pass

            new_refresh = RefreshToken.for_user(user)
            return Response(_tokens_payload(new_refresh), status=200)

        except TokenError:
            return Response({"detail": "invalid refresh"}, status=401)
        except AuthUser.DoesNotExist:
            return Response({"detail": "user not found"}, status=401)