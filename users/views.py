import logging
import secrets
import string
from rest_framework.views import APIView
from rest_framework import status
from django.db import models
from .models import User, Friendship, FriendLink
from badges.models import Badge, UserBadge
from challenges.models import ChallengeAttempt, ChallengeAttemptUser
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
from django.conf import settings
from django.shortcuts import get_object_or_404
# 유저 관련 import
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import NotFound, PermissionDenied

# 친구 요청 관련 함수
def _generate_code(length: int = 12) -> str:
    # 보안 난수 기반 Base62 코드
    alphabet = string.digits + string.ascii_uppercase + string.ascii_lowercase
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def _build_friend_url(request, code: str) -> str:
    base = getattr(settings, "FRIEND_WEB_BASE_URL", None)
    if base:
        return f"{base.rstrip('/')}/i/f/{code}"
    return request.build_absolute_uri(f"/i/f/{code}")

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

class FriendsListView(AuthedAPIView):
    # 친구 목록 조회
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
                "profileImage": profile_image,
                "isClose": f.closeFriend
            })

        return api_response(result=friends)

class FriendView(AuthedAPIView):
    # 친한 친구 설정
    def patch(self, request):
        app_user = self.get_app_user(request)

        add_id = request.data.get("add", None)
        subtract_id = request.data.get("subtract", None) # 변수명을 단수형으로 변경

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
        subtract_id = to_int_or_none(subtract_id) # 단일 값에 대해 타입 보정

        # 자기 자신 방지
        if subtract_id == app_user.userId:
            subtract_id = None
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
        to_subtract = []
        if subtract_id is not None and subtract_id in accepted_friend_ids:
            to_subtract = [subtract_id]

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
        )
    
    # 친구 검색
    def get(self, request):
        app_user = self.get_app_user(request)
        friend_name = (request.GET.get('friendName') or '').strip()

        if not friend_name:
            return api_response(
                status=status.HTTP_400_BAD_REQUEST
            )

        # 나와 수락된 친구 관계만 조회
        friendships = Friendship.objects.filter(
            (models.Q(requester=app_user) | models.Q(receiver=app_user)),
            status=Friendship.Status.ACCEPTED
        ).select_related('requester', 'receiver')

        # 친구 유저만 뽑고 중복 제거
        friends = []
        seen = set()
        for f in friendships:
            friend = f.receiver if f.requester_id == app_user.userId else f.requester
            if friend.userId in seen:
                continue
            seen.add(friend.userId)
            friends.append(friend)

        # 이름 부분일치(대소문자 무시) 필터
        name_lower = friend_name.lower()
        matched_ids = [
            u.userId
            for u in friends
            if getattr(u, 'userName', '') and name_lower in u.userName.lower()
        ]

        # 스펙에 맞춰 단일 결과는 정수, 복수는 배열로 반환
        result_value = matched_ids[0] if len(matched_ids) == 1 else matched_ids

        return api_response(
            result={"friendId": result_value}
        )
    
    # 친구 삭제
    def delete(self, request):
        app_user = self.get_app_user(request)

        raw_friend_id = request.query_params.get("friendId")
        if raw_friend_id is None or str(raw_friend_id).strip() == "":
            return api_response(
                code="COMMON400",
                message="friendId가 필요합니다.",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            friend_id = int(str(raw_friend_id).strip())
        except ValueError:
            return api_response(
                code="COMMON400",
                message="friendId는 정수여야 합니다.",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # 자기 자신 방지
        if friend_id == app_user.userId:
            return api_response(
                code="COMMON400",
                message="본인은 삭제할 수 없습니다.",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # 무방향 키로 한 쌍을 특정
        a, b = sorted([app_user.userId, friend_id])
        qs = Friendship.objects.filter(user_small=a, user_large=b)

        # 이미 친구가 아니어도 "삭제"는 멱등하게 성공 처리
        deleted_count, _ = qs.delete()

        return api_response(
            code="COMMON200",
            message="성공입니다.",
            status_code=status.HTTP_200_OK
        )
    
class FriendProfileView(AuthedAPIView):
    # 친구 프로필 조회
    def get(self, request):
        app_user = self.get_app_user(request)

        # 1) friendId 파라미터 검증
        raw_friend_id = request.query_params.get("friendId")
        if raw_friend_id is None or str(raw_friend_id).strip() == "":
            return api_response(
                status_code=status.HTTP_400_BAD_REQUEST
            )
        friend_id = int(str(raw_friend_id).strip())

        # 자기 자신 금지 예외처리
        if friend_id == app_user.userId:
            return api_response(
                code="COMMON400",
                message="본인 프로필은 이 API에서 조회할 수 없습니다.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 2) 친구 존재 확인
        try:
            friend = User.objects.get(userId=friend_id)
        except User.DoesNotExist:
            raise NotFound("해당 friendId의 유저가 없습니다.")

        # 3) 친구 관계(수락됨) 확인
        is_friend = Friendship.objects.filter(
            (
                models.Q(requester_id=app_user.userId, receiver_id=friend.userId)
                | models.Q(receiver_id=app_user.userId, requester_id=friend.userId)
            ),
            status=Friendship.Status.ACCEPTED,
        ).exists()

        if not is_friend:
            raise PermissionDenied("친구가 아니므로 조회할 수 없습니다.")

        # 4) 프로필 이미지 안전 접근 (ImageField/URL/문자열 모두 커버)
        profile_image = None
        if hasattr(friend, "profileImage") and getattr(friend, "profileImage"):
            try:
                profile_image = friend.profileImage.url  # ImageField인 경우
            except Exception:
                profile_image = friend.profileImage  # 문자열/URL인 경우

        # 5) withMe 계산: 같은 challengeAttempt에 나와 친구가 함께 참여한 고유 attempt 수
        my_attempt_ids = ChallengeAttemptUser.objects.filter(
            userId_id=app_user.userId
        ).values_list("challengeAttemptId_id", flat=True)

        with_me = (
            ChallengeAttemptUser.objects.filter(
                userId_id=friend.userId, challengeAttemptId_id__in=my_attempt_ids
            )
            .values_list("challengeAttemptId_id", flat=True)
            .distinct()
            .count()
        )

        # 6) friendSuccess 계산: 친구가 성공한 시도 수 (attemptResult=True)
        friend_success = ChallengeAttempt.objects.filter(
            userId_id=friend.userId, attemptResult=True
        ).count()

        # 7) isClose: 친한 친구 여부 포함
        # 특정 친구(friend)와의 관계만 정확히 조회합니다.
        friendship = Friendship.objects.filter(
            (
                models.Q(requester=app_user, receiver=friend)
                | models.Q(receiver=app_user, requester=friend)
            ),
            status=Friendship.Status.ACCEPTED,
        ).first()

        # friendship이 존재할 경우에만 isClose 값을 가져옵니다.
        isClose = friendship.closeFriend if friendship else False

        result = {
            "friendName": getattr(friend, "userName", None),
            "profileImage": profile_image,
            "withMe": with_me,
            "friendSuccess": friend_success,
            "isClose": isClose,
            "friendId": friend.userId  # 올바른 친구(2)의 ID
        }

        return api_response(
            result=result
        )
    
class FriendLinkMeView(AuthedAPIView):
    # 친구 요청
    def get(self, request):
        app_user = self.get_app_user(request)

        link, created = FriendLink.objects.get_or_create(
            issuer=app_user,
            defaults={"code": _generate_code()}
        )
        url = _build_friend_url(request, link.code)
        return api_response(
            result={"url": url},
            status_code=status.HTTP_200_OK
        )


class FriendLinkOpenView(AuthedAPIView):
    @transaction.atomic
    # 친구 수락
    def post(self, request):
        app_user = self.get_app_user(request)
        code = (request.data or {}).get("code")
        if not code:
            return api_response(
                code="FRIEND400_MISSING_CODE",
                message="code 값이 필요합니다.",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        link = get_object_or_404(FriendLink, code=code)
        issuer: User = link.issuer
        opener: User = app_user

        # 자기 자신 금지
        if issuer.userId == opener.userId:
            return api_response(
                code="FRIEND400_SELF",
                message="자기 자신 링크는 사용할 수 없습니다.",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # 무방향 키로 멱등/동시성 보장
        a, b = sorted([issuer.userId, opener.userId])
        friendship, created = Friendship.objects.get_or_create(
            user_small=a,
            user_large=b,
            defaults={
                "requester_id": issuer.userId,   
                "receiver_id": opener.userId,
                "status": Friendship.Status.ACCEPTED,
            },
        )

        # 기존 레코드가 pending이라면 accepted로 승격
        if not created and friendship.status != Friendship.Status.ACCEPTED:
            friendship.status = Friendship.Status.ACCEPTED
            friendship.save(update_fields=["status"])

        result_status = "AUTO_ACCEPT" if created else "ALREADY_FRIENDS"

        return api_response(
            result={
                "status": result_status,
            },
            status_code=status.HTTP_200_OK
        )

# 푸시알림을 위한 FCM 토큰 등록 
# 프론트에서 FCM 토큰을 받아 저장해야함 (유저는 로그인 상태)
class RegisterFCMTokenView(AuthedAPIView):
    def post(self, request, *args, **kwargs):

        token = request.data.get('fcm_token')
        app_user = self.get_app_user(request)
        
        # fcm_token 저장 (혹은 업데이트)
        app_user.fcm_token = token
        app_user.save(update_fields=['fcm_token'])
    
        return api_response(
            status_code=status.HTTP_200_OK
        )