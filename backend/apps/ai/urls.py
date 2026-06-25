from django.urls import path
from .views import RequestAssistantView, OfferAssistantView

urlpatterns = [
    path('request-assistant/', RequestAssistantView.as_view(), name='ai-request-assistant'),
    path('offer-assistant/', OfferAssistantView.as_view(), name='ai-offer-assistant'),
]
