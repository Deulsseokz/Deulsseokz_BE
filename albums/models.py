from django.db import models
from users.models import User
from places.models import Place
from albums.storages import PublicMediaStorage

# Create your models here.
def album_photo_path(instance, filename):
    import uuid
    import unicodedata
    import re

    def sanitize_folder_name(name: str) -> str:
        name = unicodedata.normalize("NFKD", name)
        name = re.sub(r"[^\w\s\-가-힣]", "", name)  # 한글 포함 허용
        return name.strip().replace(" ", "_")

    ext = filename.split('.')[-1]
    user_id = instance.album.userId.userId
    place_name = sanitize_folder_name(instance.album.placeId.placeName)
    return f"{user_id}/{place_name}/{uuid.uuid4().hex}.{ext}"

class Photo(models.Model):
    photoId = models.BigAutoField(primary_key=True)
    # albumId -> album으로 수정
    album = models.ForeignKey(
        'Album',
        on_delete=models.CASCADE,
        db_column='albumId',
        related_name='photos'
    )
    feelings = models.CharField(max_length=255, null=True, blank=True)
    weather = models.CharField(max_length=255, null=True, blank=True)
    photoContent = models.CharField(max_length=500, null=True, blank=True)
    date = models.DateTimeField(null=True, blank=True)
    photoUrl = models.ImageField(
        upload_to=album_photo_path,
        storage=PublicMediaStorage,
        default='photos/default.jpg'
    )


    class Meta:
        db_table = 'Photo'

    def __str__(self):
        return f"photoId: {self.photoId}"


class Album(models.Model):
    albumId = models.BigAutoField(primary_key=True)

    userId = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='userId',
        related_name='albums'
    )
    placeId = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        db_column='placeId',
        related_name='albums'
    )
    representativePhotoId = models.ForeignKey(
        Photo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='representativePhotoId',
        related_name='representative_albums'
    )

    class Meta:
        db_table = 'Album'

    def __str__(self):
        return f"albumId: {self.albumId}"