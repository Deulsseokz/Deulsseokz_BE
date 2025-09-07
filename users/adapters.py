from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.utils import perform_login
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        email = sociallogin.account.extra_data.get("email")
        if email:
            try:
                user = User.objects.get(email=email)
                # 기존 유저에 연결
                sociallogin.connect(request, user)
            except User.DoesNotExist:
                pass  # 없으면 기본 회원가입 흐름 그대로 진행

    def get_login_redirect_url(self, request):
        user = request.user
        refresh = RefreshToken.for_user(user)
        return (
            f"http://localhost:8081/auth/callback"
            f"?access={str(refresh.access_token)}"
            f"&refresh={str(refresh)}"
        )
