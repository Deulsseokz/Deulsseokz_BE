import logging
import json, time, requests
import jwt
from jwt import PyJWKClient
from django.conf import settings
from django.db import transaction
from django.utils.text import slugify
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.utils import timezone
from users.models import User as AppUser
from badges.models import UserBadge, Badge

AuthUser = get_user_model()

logger = logging.getLogger(__name__)

APPLE_ISS = "https://appleid.apple.com"
APPLE_JWKS_URL = f"{APPLE_ISS}/auth/keys"

def _build_unique_username(seed: str | None) -> str:
    base = slugify((seed or "user").split("@")[0]) or "user"
    cand = base
    i = 0
    while AuthUser.objects.filter(username=cand).exists():
        i += 1
        cand = f"{base}-{i:04d}"
    return cand

def _tokens_payload(refresh: RefreshToken):
    access = refresh.access_token
    return {
        "access": str(access),
        "refresh": str(refresh),
        "access_expires": int(access["exp"]),
        "refresh_expires": int(refresh["exp"]),
    }

def verify_apple_identity_token(id_token: str) -> dict:
    jwk_client = PyJWKClient(APPLE_JWKS_URL)
    signing_key = jwk_client.get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.APPLE_CLIENT_ID,
        issuer=APPLE_ISS,
    )
    return claims

class AppleSignInView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        id_token = request.data.get("identityToken")
        if not id_token:
            return Response({"detail": "identityToken required"}, status=400)

        # 1) Apple id_token 검증
        try:
            claims = verify_apple_identity_token(id_token)
        except Exception:
            return Response({"detail": "Invalid Apple identityToken"}, status=401)

        apple_sub = claims.get("sub")
        email = claims.get("email")  # 최초 로그인 때만 올 수 있음
        username_seed = email or f"apple-{apple_sub}"
        full_name = request.data.get("fullName")

        # apple sub 필수 (없으면 오류)
        if not apple_sub:
            return Response({"detail": "Apple sub is missing"}, status=400)

        with transaction.atomic():
            created_auth = False
            auth_user = None

            # 2-A) 1순위: apple_sub로 조회 (이메일 가리기 사용자를 포함한 모든 Apple 유저 식별)
            auth_user = AuthUser.objects.filter(apple_sub=apple_sub).first()
            
            # 2-B) 2순위: sub로 찾지 못했고, email 정보가 있다면 email로 조회 (구형 유저 호환용)
            if not auth_user and email:
                auth_user = AuthUser.objects.filter(email=email).first()

            if auth_user:
                # 유저를 찾았다면, 혹시 sub가 누락되어 있을 경우 업데이트
                if not auth_user.apple_sub:
                    auth_user.apple_sub = apple_sub
                    auth_user.save(update_fields=["apple_sub"])
            else:
                # 2-C) 완전히 새로운 유저 생성
                username_for_creation = _build_unique_username(username_seed)
                
                auth_user = AuthUser.objects.create(
                    username=username_for_creation,
                    email=email,
                    apple_sub=apple_sub, # 새로 생성 시 sub 저장
                )
                created_auth = True

            # 3) 앱 유저 1:1 보장 (필드명: auth)
            app_user = AppUser.objects.filter(auth=auth_user).first()

            if not app_user:
                backfill_name = full_name or (email or auth_user.username)
                app_user = AppUser.objects.filter(
                    auth__isnull=True, userName=backfill_name
                ).first()

            if app_user:
                if app_user.auth_id is None:
                    app_user.auth = auth_user
                    app_user.save(update_fields=["auth"])
            else:
                app_user = AppUser.objects.create(
                    auth=auth_user,  # ★ 필드명 통일
                    userName=full_name or (email or auth_user.username),
                    profileImage=None,
                    representBadgeId=1, # 가입 시 첫 만남 배지 부여
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