from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from django.contrib.auth import get_user_model

User = get_user_model()

def _set_auth_cookies(response, refresh: RefreshToken):
    access = refresh.access_token
    kw = settings.JWT_COOKIE_KWARGS
    response.set_cookie("access_token", str(access), max_age=15*60, **kw)
    # refresh 범위를 좁히고 싶으면 path를 다르게 줄 수도 있음
    response.set_cookie("refresh_token", str(refresh), max_age=7*24*3600, **kw)

@method_decorator(csrf_exempt, name="dispatch")  # 로그인은 CSRF 제외
class GoogleIdTokenLogin(APIView):
    """
    프런트에서 받은 Google idToken을 검증하고 자체 JWT(Access/Refresh)를 HttpOnly 쿠키로 발급
    Body: { "idToken": "<google id token>" }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("idToken")
        if not token:
            return Response({"detail": "idToken required"}, status=400)
        try:
            payload = google_id_token.verify_oauth2_token(
                token, google_requests.Request(), settings.GOOGLE_CLIENT_ID
            )
            if payload.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
                raise ValueError("Bad issuer")
        except Exception:
            return Response({"detail": "Invalid Google idToken"}, status=401)

        email = payload.get("email")
        username = email.split("@")[0] if email else payload.get("sub")
        user, _ = User.objects.get_or_create(
            email=email,
            defaults={"username": username},
        )

        refresh = RefreshToken.for_user(user)
        res = Response({"ok": True, "user": {"email": user.email, "username": user.username}})
        _set_auth_cookies(res, refresh)
        return res

@method_decorator(csrf_exempt, name="dispatch")  # 리프레시는 CSRF 제외(대신 경로/도메인 제한 권장)
class RotateTokenView(APIView):
    """
    쿠키의 refresh_token으로 access/refresh 회전 발급
    """
    permission_classes = [AllowAny]

    def post(self, request):
        raw = request.COOKIES.get("refresh_token")
        if not raw:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            old = RefreshToken(raw)
            new = old.rotate()
        except TokenError:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        res = Response({"ok": True})
        _set_auth_cookies(res, new)
        return res

@method_decorator(csrf_exempt, name="dispatch")
class LogoutView(APIView):
    """
    쿠키 삭제(서버 상태 무관)
    """
    def post(self, request):
        res = Response({"ok": True})
        res.delete_cookie("access_token", path="/")
        res.delete_cookie("refresh_token", path="/")
        return res
