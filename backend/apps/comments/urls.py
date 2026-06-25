from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ServiceCommentViewSet

router = DefaultRouter()
router.register(r'', ServiceCommentViewSet, basename='comments')

urlpatterns = [
    # DELETE / PATCH for comments via /api/v1/comments/{id}/
    path('', include(router.urls)),
]
