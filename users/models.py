from django.db import models
from django.conf import settings

class User(models.Model):
    userId = models.BigAutoField(primary_key=True)

    auth = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",     # auth_user.profile 로 접근 가능
        null=True, blank=True,      # 기존 데이터 호환 위해 초기엔 허용
        db_column="auth_user_id",
    )

    userName = models.CharField(max_length=255, null=True, blank=True)
    profileImage = models.CharField(max_length=500, null=True, blank=True, db_column='profileImage')
    representBadge = models.ForeignKey('badges.UserBadge', related_name='representBadgeId', on_delete=models.CASCADE, null=True)

    class Meta:
        db_table = 'User'

    def __str__(self):
        return self.userName or f"User {self.userId}"

class Friendship(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'
        BLOCKED = 'blocked', 'Blocked'

    requester = models.ForeignKey(User, related_name='sent_friend_requests', on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name='received_friend_requests', on_delete=models.CASCADE)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_column='status'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    closeFriend = models.BooleanField(default=False)

    user_small = models.BigIntegerField(editable=False, db_index=True, null=True)
    user_large = models.BigIntegerField(editable=False, db_index=True, null=True)

    class Meta:
        db_table = 'Friendship'
        constraints = [
            models.CheckConstraint(
                check=models.Q(user_small__lt=models.F('user_large')),
                name='friendship_chk_order',
            ),
            models.UniqueConstraint(
                fields=['user_small', 'user_large'],
                name='friendship_uq_pair',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'user_small'], name='fx_status_small'),
            models.Index(fields=['status', 'user_large'], name='fx_status_large'),
        ]

    def save(self, *args, **kwargs):
        a, b = self.requester_id, self.receiver_id
        if a == b:
            raise ValueError("self friendship not allowed")
        self.user_small, self.user_large = (a, b) if a < b else (b, a)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.requester} → {self.receiver} ({self.status})"
    
class FriendLink(models.Model):
    issuer = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="friend_link"
    )                        
    code = models.CharField(max_length=32, unique=True) 
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "FriendLink"