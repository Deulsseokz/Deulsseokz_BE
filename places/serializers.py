from rest_framework import serializers
from .models import Place

class favoritePlaceSerializer(serializers.ModelSerializer):
    place = serializers.CharField(required=True)
    isFavorite = serializers.BooleanField(required=True)

    class Meta:
        model = Place
        fields = ['place', 'isFavorite']