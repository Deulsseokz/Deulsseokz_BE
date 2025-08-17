from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from django.contrib.auth import get_user_model

User = get_user_model()

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
    """프런트에서 받은 Google idToken을 검증하고, 토큰을 JSON으로 반환"""
    permission_classes = [AllowAny]

    def post(self, request):
        id_token_str = request.data.get("idToken")
        if not id_token_str:
            return Response({"detail": "idToken required"}, status=400)

        try:
            payload = google_id_token.verify_oauth2_token(
                id_token_str, google_requests.Request(), settings.GOOGLE_CLIENT_ID
            )
            if payload.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
                raise ValueError("Bad issuer")
        except Exception:
            return Response({"detail": "Invalid Google idToken"}, status=401)

        email = payload.get("email")
        username = email.split("@")[0] if email else payload.get("sub")
        user, _ = User.objects.get_or_create(email=email, defaults={"username": username})

        refresh = RefreshToken.for_user(user)
        body = {"ok": True, "user": {"email": user.email, "username": user.username}}
        body.update(_tokens_payload(refresh))
        return Response(body, status=200)

class RotateTokenView(APIView):
    """리프레시 토큰으로 재발급(JSON 반환). 쿠키 사용 안 함."""
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