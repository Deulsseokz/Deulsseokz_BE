import logging
from rest_framework.views import APIView
from rest_framework import status
from django.db import models
from .models import User, Friendship
from badges.models import Badge, UserBadge
from .serializers import MypageInfoSerializer
from utils.response_wrapper import api_response
logger = logging.getLogger(__name__)

# 마이페이지 정보 조회
class MypageView(APIView):
    def get(self, request):
        try:
            user = User.objects.get(userId=1)
        except User.DoesNotExist:
            return api_response(
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        result = []
        userName = user.userName
        profileImage = user.profileImage
        badgeImage = user.representBadge
        serializer = MypageInfoSerializer(user)
        result.append(serializer.data)

        return api_response(result=result)

# 친구 목록 조회
class FriendsListView(APIView):
    def get(self, request):
        try: 
            user = User.objects.get(userId=1)
        except User.DoesNotExist:
            return api_response(
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # 친구 요청의 양방향 모두 accepted된 친구 조회
        friendships = Friendship.objects.filter(
            models.Q(requester=user) | models.Q(receiver=user),
            status=Friendship.Status.ACCEPTED
        )

        friend_ids = []
        friend_names = []

        for f in friendships:
            friend = f.receiver if f.requester == user else f.requester
            friend_ids.append(friend.userId)
            friend_names.append(friend.userName)

        return api_response(
            result={
                "userId": friend_ids,
                "friendsName": friend_names
            }
        )