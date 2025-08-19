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
        email = claims.get("email")  # 최초 로그인 때만 올 수 있음
        username_seed = email or f"apple-{apple_sub}"
        full_name = request.data.get("fullName")

        with transaction.atomic():
            # 2) 인증 유저 upsert
            if email:
                auth_user, created_auth = AuthUser.objects.get_or_create(
                    email=email,
                    defaults={"username": _build_unique_username(username_seed)},
                )
            else:
                # 이메일이 안 오는 케이스(Private Relay 등)
                auth_user, created_auth = AuthUser.objects.get_or_create(
                    username=_build_unique_username(username_seed),
                    defaults={"email": None},
                )

            # 3) 앱 유저 1:1 보장
            #   3-1) 이미 연결된 AppUser가 있나?
            app_user = AppUser.objects.filter(authUser=auth_user).first()

            if not app_user:
                #   3-2) (선택) 레거시 행 백필 시도: userName이 fullName/username과 동일하고 아직 미연결인 경우
                backfill_name = full_name or (email or auth_user.username)
                app_user = AppUser.objects.filter(
                    authUser__isnull=True, userName=backfill_name
                ).first()

            if app_user:
                if app_user.authUser_id is None:
                    app_user.authUser = auth_user
                    # profileImage가 비어 있고 나중에 채우고 싶다면 여기서 기본값/유지 선택
                    app_user.save(update_fields=["authUser"])
            else:
                #   3-3) 새로 생성하면서 반드시 연결
                app_user = AppUser.objects.create(
                    authUser=auth_user,                  
                    userName=full_name or (email or auth_user.username),
                    profileImage=None,                          # 필요 시 기본 이미지 경로
                )

        # 4) 자체 토큰 발급 + isNew 포함해 JSON 반환
        refresh = RefreshToken.for_user(auth_user)
        body = {
            "ok": True,
            "isNew": created_auth,  # 인증 유저 기준 신규 여부
            # "user": {
            #     "userId": app_user.userId,
            #     "userName": app_user.userName,
            #     "profileImage": app_user.profileImage,
            # },
        }
        body.update(_tokens_payload(refresh))
        return Response(body, status=200)