"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.contrib import admin
from django.urls import path
from django.conf.urls import include

schema_view = get_schema_view(
   openapi.Info(
      title="Deulsseokz API",
      default_version='v1',
      description="들썩즈 API 문서입니다.",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="your@email.com"),
      license=openapi.License(name="MIT License"),
   ),
   public=True,
   permission_classes=[permissions.AllowAny],
   url="https://melog.store",
)

urlpatterns = [
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('admin/', admin.site.urls),
    path('challenge/', include('challenges.urls')),
    path('place/', include('places.urls')),
    path('', include('albums.urls')), # 앨범 및 사진은 내부에서 처리 (다른 것은 이렇게 처리하면 안 됨)
    path('mypage/', include('users.urls')),
    path('friends/', include('users.urls')),
    path('point', include('points.urls')),
]
