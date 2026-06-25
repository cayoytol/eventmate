from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BillingViewSet, PlanViewSet, BillingWebhookView, PayPalSubscriptionReturnView, PayPalSubscriptionCaptureView, SubscriptionQuoteView

router = DefaultRouter()
router.register('plans', PlanViewSet, basename='plans')
router.register('', BillingViewSet, basename='billing')

urlpatterns = [
    # Explicit URL registrations (before router to avoid shadowing)
    path('paypal/return/', PayPalSubscriptionReturnView.as_view(), name='paypal-billing-return'),
    path('paypal/capture/', PayPalSubscriptionCaptureView.as_view(), name='paypal-billing-capture'),
    path('webhook/<str:provider>/', BillingWebhookView.as_view(), name='billing-webhook'),
    path('subscription/payments/<int:payment_id>/status/', BillingViewSet.as_view({'get': 'payment_status'}), name='billing-payment-status'),
    path('subscription/payments/', BillingViewSet.as_view({'get': 'payment_history'}), name='billing-payment-history'),
    path('subscription/quote/', SubscriptionQuoteView.as_view(), name='billing-subscription-quote'),
    path('subscription/checkout/', BillingViewSet.as_view({'post': 'checkout'}), name='billing-checkout'),
    path('', include(router.urls)),
]
