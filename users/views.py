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
from django.db import transaction, models
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

class FriendView(AuthedAPIView):
    # 친한 친구 설정
    def patch(self, request):
        app_user = self.get_app_user(request)

        add_id = request.data.get("add", None)
        subtract_ids = request.data.get("subtract", None)

        # ---- 타입 보정: "7" -> 7 허용 ----
        def to_int_or_none(v):
            if v is None:
                return None
            if isinstance(v, int):
                return v
            if isinstance(v, str) and v.strip().isdigit():
                return int(v.strip())
            return None  # 잘못된 타입

        add_id = to_int_or_none(add_id)

        if isinstance(subtract_ids, list):
            subtract_ids = [to_int_or_none(x) for x in subtract_ids if to_int_or_none(x) is not None]
        elif subtract_ids is None:
            subtract_ids = []
        else:
            subtract_ids = [to_int_or_none(subtract_ids)] if to_int_or_none(subtract_ids) is not None else []

        # 자기 자신 방지
        subtract_ids = [i for i in subtract_ids if i != app_user.userId]
        if add_id == app_user.userId:
            add_id = None

        # 수락된 친구 집합 (양방향) — _id 컬럼으로 단순화
        accepted_friend_ids = set(
            Friendship.objects.filter(
                models.Q(requester_id=app_user.userId) | models.Q(receiver_id=app_user.userId),
                status=Friendship.Status.ACCEPTED
            ).values_list(
                models.Case(
                    models.When(requester_id=app_user.userId, then="receiver_id"),
                    default="requester_id",
                    output_field=models.IntegerField()
                ),
                flat=True
            )
        )

        # subtract 우선
        to_subtract = [uid for uid in subtract_ids if uid in accepted_friend_ids]
        to_add = []
        if add_id is not None and add_id in accepted_friend_ids and add_id not in to_subtract:
            to_add = [add_id]

        def filter_pair(owner_id, target_ids):
            # (_id 컬럼만 사용)
            return (
                (models.Q(requester_id=owner_id) & models.Q(receiver_id__in=target_ids)) |
                (models.Q(receiver_id=owner_id) & models.Q(requester_id__in=target_ids))
            )

        removed = added = 0
        with transaction.atomic():
            if to_subtract:
                removed = Friendship.objects.filter(
                    filter_pair(app_user.userId, to_subtract),
                    status=Friendship.Status.ACCEPTED
                ).update(closeFriend=False)

            if to_add:
                added = Friendship.objects.filter(
                    filter_pair(app_user.userId, to_add),
                    status=Friendship.Status.ACCEPTED
                ).update(closeFriend=True)

        return api_response(
            code="COMMON200",
            message="성공입니다.",
            status_code=status.HTTP_200_OK
        )