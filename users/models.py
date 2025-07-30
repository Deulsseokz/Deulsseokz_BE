from django.db import models

class User(models.Model):
    userId = models.BigAutoField(primary_key=True)
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

    class Meta:
        db_table = 'Friendship'
        unique_together = ('requester', 'receiver')  # 중복 요청 방지

    def __str__(self):
        return f"{self.requester} → {self.receiver} ({self.status})"