from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaymentViewSet, CreateOrderPaymentView, OrderPaymentStatusView, PaymentWebhookView, PayPalOrderReturnView, PayPalOrderCaptureView, OrderPaymentQuoteView

router = DefaultRouter()
router.register('', PaymentViewSet, basename='payments')

urlpatterns = [
    path('paypal/return/', PayPalOrderReturnView.as_view(), name='paypal-order-return'),
    path('paypal/capture/', PayPalOrderCaptureView.as_view(), name='paypal-order-capture'),
    path('orders/<int:order_id>/quote/', OrderPaymentQuoteView.as_view(), name='order-payment-quote'),
    path('orders/<int:order_id>/create/', CreateOrderPaymentView.as_view(), name='order-payment-create'),
    path('orders/<int:order_id>/status/', OrderPaymentStatusView.as_view(), name='order-payment-status'),
    path('webhook/<str:provider>/', PaymentWebhookView.as_view(), name='payment-webhook'),
    path('', include(router.urls)),
]

