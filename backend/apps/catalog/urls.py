from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ServiceViewSet, GeocodeView, ReverseGeocodeView

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='categories')
router.register(r'services', ServiceViewSet, basename='services')

urlpatterns = [
    path('geo/geocode/', GeocodeView.as_view(), name='geo-geocode'),
    path('geo/reverse-geocode/', ReverseGeocodeView.as_view(), name='geo-reverse-geocode'),
    path('', include(router.urls)),
]
