from rest_framework_simplejwt.authentication import JWTAuthentication

class CookieJWTAuthentication(JWTAuthentication):
    """
    Authorization 헤더가 없으면 HttpOnly 쿠키의 access_token으로 인증한다.
    """
    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            return super().authenticate(request)

        raw = request.COOKIES.get("access_token")
        if not raw:
            return None
        validated = self.get_validated_token(raw)
        return (self.get_user(validated), validated)
