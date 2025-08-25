import logging
from rest_framework.views import APIView
from rest_framework import status
from django.db import models
from .models import User, Friendship
from badges.models import Badge, UserBadge
from .serializers import MypageInfoSerializer
from utils.response_wrapper import api_response
logger = logging.getLogger(__name__)
from rest_framework.permissions import IsAuthenticated
from allauth.socialaccount.providers.oauth2.views import OAuth2Adapter
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from dj_rest_auth.registration.views import SocialLoginView
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import redirect
# 유저 관련 import
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import NotFound, PermissionDenied

# 유저 관련 공통 베이스 뷰
class AuthedAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_app_user(self, request) -> User:
        try:
            return User.objects.get(auth=request.user)
        except User.DoesNotExist:
            raise NotFound("연결된 사용자 프로필이 없습니다.")

# 유저 정보 조회
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        result = {
            "email": request.user.email,
            "username": request.user.username,
        }
        return api_response(result=result)


class MypageView(AuthedAPIView):
    # 마이페이지 정보 조회
    def get(self, request):
        app_user = self.get_app_user(request)
        serializer = MypageInfoSerializer(app_user)
        return api_response(result=serializer.data)
    
    # 마이페이지 정보 수정
    def patch(self, request):
        app_user = self.get_app_user(request)

        # null 아닌 필드만 업데이트
        update_fields = ['userName', 'profileImage']
        for field in update_fields:
            if field in request.data and request.data[field] is not None:
                setattr(app_user, field, request.data[field])
        app_user.save()

        return api_response(
            result="유저 정보가 성공적으로 수정되었습니다.",
            status_code=status.HTTP_200_OK
        )

# 친구 목록 조회
class FriendsListView(AuthedAPIView):
    def get(self, request):
        app_user = self.get_app_user(request)

        # 친구 요청의 양방향 모두 accepted된 친구 조회
        friendships = Friendship.objects.filter(
            models.Q(requester=app_user) | models.Q(receiver=app_user),
            status=Friendship.Status.ACCEPTED
        )

        friend_ids = []
        friend_names = []

        for f in friendships:
            friend = f.receiver if f.requester == app_user else f.requester
            friend_ids.append(friend.userId)
            friend_names.append(friend.userName)

        return api_response(
            result={
                "userId": friend_ids,
                "friendsName": friend_names
            }
        )# 친구 목록 조회
class FriendsListView(AuthedAPIView):
    def get(self, request):
        app_user = self.get_app_user(request)

        # 친구 요청의 양방향 모두 accepted된 친구 조회
        friendships = Friendship.objects.filter(
            models.Q(requester=app_user) | models.Q(receiver=app_user),
            status=Friendship.Status.ACCEPTED
        )

        friends = []
        seen = set()  # 중복 방지 (혹시 양방향 레코드가 존재할 경우)

        for f in friendships:
            friend = f.receiver if f.requester_id == app_user.userId else f.requester
            if friend.userId in seen:
                continue
            seen.add(friend.userId)

            # profileImage 필드 안전 접근 (ImageField/URL/문자열 모두 커버)
            profile_image = None
            # profileImage
            if hasattr(friend, 'profileImage') and getattr(friend, 'profileImage'):
                try:
                    profile_image = friend.profileImage.url  # ImageField인 경우
                except Exception:
                    profile_image = friend.profileImage  # 문자열/URL인 경우

            friends.append({
                "userId": friend.userId,
                "friendsName": friend.userName,
                "profileImage": profile_image
            })

        return api_response(result=friends)