import requests
import logging
import re
import json
from django.core.files.base import ContentFile
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.views import APIView
from rest_framework import status
from .models import User, Challenge, ChallengeAttempt, ChallengeAttemptUser
from albums.models import Album, Photo
from places.models import FavoritePlace, Place
from .serializers import ChallengeResponseSerializer, ChallengeAttemptRequestSerializer, ChallengeAttemptSerializer
from .query_serializers import ChallengeQuerySerializer
from utils.response_wrapper import api_response
from django.db import transaction
from .tasks import process_challenge_attempt
from django.db.models import Count, Case, When, F, FloatField
from django.db.models.functions import Cast
from django.shortcuts import get_object_or_404
logger = logging.getLogger(__name__)

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

# 전체 챌린지 목록 조회
class ChallengeListView(AuthedAPIView):
    def get(self, request):
        app_user = self.get_app_user(request)
        
        result = []
        challenges = Challenge.objects.all()

        for challenge in challenges:
            # 해당 유저의 성공한 도전 이력이 있는지 확인
            attempt = ChallengeAttempt.objects.filter(
                userId=app_user,
                challengeId=challenge,
                attemptResult=True
            ).order_by('-attemptDate').first()

            result.append({
                "challengeId": challenge.challengeId,
                "placeName": challenge.placeId.placeName,
                "isChallenged": attempt is not None,
                "challengePhoto": attempt.attemptImage.url if attempt else None,
                "location": challenge.placeId.location
            })

        return api_response(
            result=result
        )

# 챌린지 정보 조회
class ChallengeInfoView(AuthedAPIView):
    def get(self, request):
        app_user = self.get_app_user(request)

        query_serializer = ChallengeQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)

        validated_data = query_serializer.validated_data
        placeName = validated_data.get('place', None)
        placeId = validated_data.get('placeId', None)

        if not placeName and not placeId:
            return api_response(
                code="INVALID_QUERY",
                message="place 또는 placeId 중 하나는 필수입니다.",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # Case 1: placeId 기반 단일 조회
        if placeId:
            challenges = Challenge.objects.select_related('placeId').filter(placeId__placeId=placeId)

            if not challenges.exists():
                return api_response(
                    code="CHALLENGE_NOT_FOUND",
                    message="해당 ID에 대한 챌린지 정보가 없습니다.",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            favorite_place_ids = set(
                FavoritePlace.objects.filter(userId=app_user).values_list('placeId', flat=True)
            )

            result = []
            for challenge in challenges:
                placeName = challenge.placeId.placeName
                is_favorite = challenge.placeId.placeId in favorite_place_ids
                serializer = ChallengeResponseSerializer(challenge, context={'is_favorite': is_favorite})
                result.append(serializer.data)

            return api_response(result=result)

        # Case 2: placeName 기반 다중 조회
        else:
            challenges = Challenge.objects.select_related('placeId').filter(placeId__placeName__icontains=placeName)

            if not challenges.exists():
                return api_response(
                    code="CHALLENGE_NOT_FOUND",
                    message=f"'{placeName}'을 포함하는 장소에 대한 챌린지가 없습니다.",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            favorite_place_ids = set(
                FavoritePlace.objects.filter(userId=app_user).values_list('placeId', flat=True)
            )

            result = []
            for challenge in challenges:
                placeName = challenge.placeId.placeName
                is_favorite = challenge.placeId.placeId in favorite_place_ids
                serializer = ChallengeResponseSerializer(challenge, context={'is_favorite': is_favorite})
                result.append(serializer.data)

            return api_response(result=result)

# 챌린지 도전
class ChallengeAttemptView(AuthedAPIView):
    @swagger_auto_schema(request_body=ChallengeAttemptRequestSerializer)
    def post(self, request):
        app_user = self.get_app_user(request)

        serializer = ChallengeAttemptRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        place = data.get('place')
        attemptImage = data.get('attemptImage')
        attemptDate = data.get('attemptDate')
        friend_ids = data.get('friends', []) # 친구 ID 리스트를 여기서 파싱합

        try:
            challenge = Challenge.objects.get(placeId__placeName=place)
        except Challenge.DoesNotExist:
            return api_response(
                code="CHALLENGE_NOT_FOUND",
                message=f"장소 '{place}'에 해당하는 챌린지가 없습니다.",
                status_code=status.HTTP_404_NOT_FOUND
            )

        # "처리 대기중" 상태의 메인 레코드(요청자 기준)를 하나 생성
        main_attempt = ChallengeAttempt.objects.create(
            challengeId=challenge,
            userId=app_user,
            attemptImage=attemptImage,
            attemptDate=attemptDate,
            status=ChallengeAttempt.AttemptStatus.PENDING
        )
        # Celery Task 호출 시, 메인 시도 ID와 함께 친구 ID 리스트를 전달
        process_challenge_attempt.delay(main_attempt.pk, friend_ids)

        logger.info(f"챌린지 시도 ID {main_attempt.pk} (친구 {len(friend_ids)}명 포함)가 큐에 추가됨.")

        # 사용자에게는 즉시 응답을 보냄
        return api_response(
            code="CHALLENGE_SUBMITTED",
            message="챌린지 사진을 성공적으로 접수했습니다. 분석이 완료되면 알려드릴게요!",
            status_code=status.HTTP_202_ACCEPTED,
            result={
                "attemptId": main_attempt.pk,
                "status": "PENDING",
                "result_url": f"/challenge/result/{main_attempt.pk}/"
            }
        )
# 챌린지 결과 조회 View (신규 클래스)
class ChallengeResultView(AuthedAPIView):
    def get(self, request, attempt_id):
        app_user = self.get_app_user(request)
        
        # 본인의 챌린지 시도 기록만 조회 가능하도록 함
        attempt = get_object_or_404(ChallengeAttempt, pk=attempt_id, userId=app_user)
        
        # 아직 분석 중인 경우
        if attempt.status in [ChallengeAttempt.AttemptStatus.PENDING, ChallengeAttempt.AttemptStatus.PROCESSING]:
            return api_response(
                code="PROCESSING",
                message="분석이 아직 진행 중입니다. 잠시 후 다시 시도해주세요.",
                status_code=status.HTTP_202_ACCEPTED,
                result={"status": attempt.status}
            )
        
        # 분석이 완료된 경우, 요청한 최종 응답 형식으로 가공
        # 이전 도전 횟수 계산
        previous_attempts_count = ChallengeAttempt.objects.filter(
            userId=app_user, 
            challengeId=attempt.challengeId,
            pk__lt=attempt.pk # 현재 시도보다 이전에 생성된 것만 카운트
        ).count()
        current_attempt_number = previous_attempts_count + 1

        result_payload = {
            "attemptResult": attempt.attemptResult,
            "attempt": current_attempt_number,
            "resultComment": attempt.resultComment,
            # DB에 저장된 상세 결과를 사용
            "condition1": attempt.result_details.get('condition1_met', False),
            "condition2": attempt.result_details.get('condition2_met', False),
        }

        return api_response(result=result_payload)
    
# 지역별 정복 현황
class ChallengeLocalView(AuthedAPIView):
    def get(self, request):
        app_user = self.get_app_user(request)

        area_name_map = {
            "서울": "Seoul",
            "인천": "Incheon",
            "경기 서부": "Gyeonggi-West",
            "경기 동부": "Gyeonggi-East",
            "경기 북부": "Gyeonggi-North",
            "경기 남부": "Gyeonggi-South",
            "강원": "Gangwon",
            "충북": "Chungbuk",
            "충남": "Chungnam",
            "전북": "Jeonbuk",
            "광주・전남": "Gwangju-Jeonnam",
            "대구・경북": "Daegu-Gyeongbuk",
            "부산・울산・경남": "Busan-Ulsan-Gyeongnam",
            "울릉도": "Ulleungdo",
            "제주도": "Jejudo"
        }

        # 해당 유저의 지역별 통계 계산
        # 1. 지역별로 존재하는 모든 챌린지의 총 개수를 계산
        total_challenges_per_area = Challenge.objects.values(
            'placeId__area' # 지역별로 그룹화
        ).annotate(
            total_count=Count('challengeId')
        ).order_by()

        # 딕셔너리 형태로 변환
        total_counts = {
            item['placeId__area']: item['total_count'] for item in total_challenges_per_area
        }

        # 2. 해당 유저가 각 지역별로 성공한 챌린지의 개수를 계산
        successful_challenges_per_area = ChallengeAttempt.objects.filter(
            userId=app_user,
            status=ChallengeAttempt.AttemptStatus.SUCCESS
        ).values(
            'challengeId__placeId__area' # 지역별로 그룹화
        ).annotate(
            # challengeId를 기준으로 고유한 개수를 셈
            successful_unique_count=Count('challengeId', distinct=True)
        ).order_by()

        # 딕셔너리 형태로 변환
        success_counts = {
            item['challengeId__placeId__area']: item['successful_unique_count'] for item in successful_challenges_per_area
        }

        # 3. 모든 지역을 포함하여 정복률 계산
        result_data = {}
        for korean_name, english_name in area_name_map.items():
            total = total_counts.get(korean_name, 0) # 해당 지역의 전체 챌린지 수
            successful = success_counts.get(korean_name, 0) # 해당 지역에서 성공한 고유 챌린지 수

            if total > 0:
                conquest_rate = (successful / total) * 100
            else:
                conquest_rate = 0
            result_data[english_name] = round(conquest_rate, 2)

        return api_response(result=result_data)
    
# 지역별 챌린지 현황 상세 조회
class ChallengeStatusByRegionView(AuthedAPIView):
    def get(self, request):
        app_user = self.get_app_user(request)

        area_name_map = {
            "서울": "Seoul",
            "인천": "Incheon",
            "경기 서부": "Gyeonggi-West",
            "경기 동부": "Gyeonggi-East",
            "경기 북부": "Gyeonggi-North",
            "경기 남부": "Gyeonggi-South",
            "강원": "Gangwon",
            "충북": "Chungbuk",
            "충남": "Chungnam",
            "전북": "Jeonbuk",
            "광주・전남": "Gwangju-Jeonnam",
            "대구・경북": "Daegu-Gyeongbuk",
            "부산・울산・경남": "Busan-Ulsan-Gyeongnam",
            "울릉도": "Ulleungdo",
            "제주도": "Jejudo"
        }

        # 1. 현재 유저가 성공한 모든 챌린지 ID를 Set 형태로 조회
        successful_challenge_ids = set(
            ChallengeAttempt.objects.filter(
                userId=app_user,
                status=ChallengeAttempt.AttemptStatus.SUCCESS
            ).values_list('challengeId_id', flat=True)
        )

        # 2. 모든 챌린지 정보를 미리 가져와서 지역별로 그룹화 (DB 호출 최소화)
        # select_related를 사용하여 Place 정보까지 한 번의 쿼리로 가져옴
        all_challenges = Challenge.objects.select_related('placeId').order_by('placeId__area')
        
        challenges_by_area = {}
        for challenge in all_challenges:
            # DB에 저장된 지역 이름을 키로 사용
            area_key = challenge.placeId.area
            if area_key not in challenges_by_area:
                challenges_by_area[area_key] = []
            
            challenges_by_area[area_key].append({
                "placeName": challenge.placeId.placeName,
                "isCompleted": challenge.challengeId in successful_challenge_ids
            })

        result = []
        for korean_name, english_name in area_name_map.items():
            # 해당 지역에 할당된 챌린지 목록 없으면 빈 리스트를 사용
            challenges_in_region = challenges_by_area.get(korean_name, [])
            
            result.append({
                "regionName": english_name,
                "challenges": challenges_in_region
            })

        return api_response(result=result)
    
# 모든 챌린지별 성공 현황 조회 (key-value 반환)
class ChallengeCompletionStatusView(AuthedAPIView):
    def get(self, request):
        app_user = self.get_app_user(request)

        area_name_map = {
            "서울": "Seoul",
            "인천": "Incheon",
            "경기 서부": "Gyeonggi-West",
            "경기 동부": "Gyeonggi-East",
            "경기 북부": "Gyeonggi-North",
            "경기 남부": "Gyeonggi-South",
            "강원": "Gangwon",
            "충북": "Chungbuk",
            "충남": "Chungnam",
            "전북": "Jeonbuk",
            "광주・전남": "Gwangju-Jeonnam",
            "대구・경북": "Daegu-Gyeongbuk",
            "부산・울산・경남": "Busan-Ulsan-Gyeongnam",
            "울릉도": "Ulleungdo",
            "제주도": "Jejudo"
        }

        # 1. 현재 유저가 성공한 모든 챌린지 ID를 Set 형태로 조회
        successful_challenge_ids = set(
            ChallengeAttempt.objects.filter(
                userId=app_user,
                status=ChallengeAttempt.AttemptStatus.SUCCESS
            ).values_list('challengeId_id', flat=True)
        )

        # 2. 모든 챌린지 정보를 미리 가져와서 지역별 객체(Object)로 그룹화
        all_challenges = Challenge.objects.select_related('placeId').order_by('placeId__area')
        
        challenges_by_area = {}
        for challenge in all_challenges:
            area_key = challenge.placeId.area
            
            # 해당 지역 키가 없으면 빈 객체로 초기화
            if area_key not in challenges_by_area:
                challenges_by_area[area_key] = {}
            
            # { "장소이름": 성공여부 } 형태의 Key-Value 쌍 추가
            place_name = challenge.placeId.placeName
            is_completed = challenge.challengeId in successful_challenge_ids
            challenges_by_area[area_key][place_name] = is_completed

        result = []
        for korean_name, english_name in area_name_map.items():
            challenges_object = challenges_by_area.get(korean_name, {})
            
            result.append({
                "regionName": english_name,
                "challenges": challenges_object
            })

        return api_response(result=result)