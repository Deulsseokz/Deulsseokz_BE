from django.db import models

# Create your models here.
class User(models.Model):
    userId = models.BigAutoField(primary_key=True)
    userName = models.CharField(max_length=255, null=True, blank=True)
    requesterId = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='requesterId',
        related_name='sent_requests',
        help_text="친구 요청 보낸 사람"
    )
    receiverId = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='receiverId',
        related_name='received_requests',
        help_text="친구 요청 받은 사람"
    )

    neighborStatus = models.CharField(
        max_length=10,
        choices=[
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
            ('blocked', 'Blocked'),
        ],
        null=True,
        blank=True,
        db_column='neighborStatus',
        help_text="친구 상태"
    )

    profileImage = models.CharField(max_length=500, null=True, blank=True, db_column='profileImage')

    class Meta:
        db_table = 'User'

    def __str__(self):
        return self.userName 
