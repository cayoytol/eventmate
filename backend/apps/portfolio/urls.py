from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PortfolioItemViewSet, PortfolioMediaViewSet

router = DefaultRouter()
router.register(r'items', PortfolioItemViewSet, basename='portfolio-items')
router.register(r'media', PortfolioMediaViewSet, basename='portfolio-media')

urlpatterns = [
    path('', include(router.urls)),
    # Requirement: GET /api/v1/providers/{id}/portfolio/
    path('providers/<int:provider_id>/portfolio/', 
         PortfolioItemViewSet.as_view({'get': 'provider_portfolio'}), 
         name='provider-portfolio'),
]
