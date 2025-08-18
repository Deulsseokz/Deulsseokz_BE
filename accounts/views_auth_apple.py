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

from users.models import User as AppUser  # 앱 유저(기존 모델)

AuthUser = get_user_model()

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
    """
    Apple의 id_token(JWT)을 공개키(JWKS)로 검증하고 클레임을 돌려줍니다.
    - alg: RS256
    - iss: https://appleid.apple.com
    - aud: settings.APPLE_CLIENT_ID (iOS 앱이면 Bundle ID)
    """
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

# (선택) authorizationCode 교환을 쓰고 싶다면 Apple client_secret 생성
def build_apple_client_secret() -> str:
    """
    Apple 토큰 엔드포인트(/auth/token) 호출에 필요한 client_secret(JWT, ES256) 생성.
    """
    now = int(time.time())
    headers = {"kid": settings.APPLE_KEY_ID}
    payload = {
        "iss": settings.APPLE_TEAM_ID,
        "iat": now,
        "exp": now + 60 * 60 * 30,  # 30시간 유효(권장 범위 내에서)
        "aud": APPLE_ISS,
        "sub": settings.APPLE_CLIENT_ID,
    }
    return jwt.encode(
        payload,
        settings.APPLE_PRIVATE_KEY,
        algorithm="ES256",
        headers=headers,
    )

# (선택) authorizationCode -> (id_token, access_token, refresh_token) 교환
def exchange_authorization_code(auth_code: str) -> dict:
    data = {
        "client_id": settings.APPLE_CLIENT_ID,
        "client_secret": build_apple_client_secret(),
        "code": auth_code,
        "grant_type": "authorization_code",
    }
    resp = requests.post(f"{APPLE_ISS}/auth/token", data=data, timeout=10)
    resp.raise_for_status()
    return resp.json()

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
        email = claims.get("email")  # 최초 로그인 때만 내려올 수 있음
        username_seed = email or f"apple-{apple_sub}"

        # 2) 우리 auth user 생성/조회
        with transaction.atomic():
            if email:
                auth_user, created = AuthUser.objects.get_or_create(
                    email=email,
                    defaults={"username": _build_unique_username(username_seed)},
                )
            else:
                auth_user, created = AuthUser.objects.get_or_create(
                    username=_build_unique_username(username_seed),
                    defaults={"email": None},
                )

            # 3) 최초 가입이면 앱 유저(users.User)에도 한 줄 생성
            app_user_id = None
            if created:
                app_user = AppUser.objects.create(
                    userName=request.data.get("fullName")
                             or email
                             or auth_user.username,
                    profileImage=None,   # 원하면 기본 이미지 경로
                )
                app_user_id = app_user.userId

        # 4) 자체 토큰 발급 + isNew 포함해 JSON 반환
        refresh = RefreshToken.for_user(auth_user)
        body = {
            "ok": True,
            "isNew": created,   # 신규면 True, 재로그인면 False
            # 필요하면 유저 정보도 함께
            # "user": {
            #     "email": auth_user.email,
            #     "username": auth_user.username,
            #     "userId": app_user_id,  # 신규 때만 값이 있을 수 있음
            # }
        }
        body.update(_tokens_payload(refresh))
        return Response(body, status=200)
