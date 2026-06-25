from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EventRequestViewSet, OfferViewSet, OrderViewSet, ReviewViewSet

router = DefaultRouter()
router.register(r'requests', EventRequestViewSet, basename='requests')
router.register(r'offers', OfferViewSet, basename='offers')
router.register(r'orders', OrderViewSet, basename='orders')
router.register(r'reviews', ReviewViewSet, basename='reviews')

urlpatterns = [
    path('', include(router.urls)),
    # Specific path for provider reviews listing
    path('providers/<int:provider_id>/reviews/', 
         ReviewViewSet.as_view({'get': 'list'}), 
         name='provider-reviews'),
]

