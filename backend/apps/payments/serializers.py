from rest_framework import serializers
from .models import Payment, PaymentTransaction


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment"""
    
    class Meta:
        model = Payment
        fields = (
            'id', 'provider_profile', 'subscription', 'amount', 
            'currency', 'status', 'created_at', 'paid_at'
        )
        read_only_fields = ('id', 'provider_profile', 'status', 'created_at', 'paid_at')


class CreatePaymentSerializer(serializers.Serializer):
    """Input serializer for creating payment"""
    subscription_id = serializers.IntegerField()
    
    def validate_subscription_id(self, value):
        from apps.billing.models import Subscription
        
        try:
            subscription = Subscription.objects.get(id=value)
        except Subscription.DoesNotExist:
            raise serializers.ValidationError("Subscription not found")
        
        # Check if subscription belongs to current user
        request = self.context.get('request')
        if request and hasattr(request.user, 'provider_profile'):
            if subscription.provider_profile != request.user.provider_profile:
                raise serializers.ValidationError("Subscription does not belong to you")
        
        # Check if subscription already has a paid payment
        if subscription.payments.filter(status=Payment.Status.PAID).exists():
            raise serializers.ValidationError("Subscription already paid")
        
        return value


class PaymentTransactionSerializer(serializers.ModelSerializer):
    """Safe serializer for PaymentTransaction, excluding raw_response/secrets"""
    retry_after = serializers.IntegerField(source='checkout_retry_after', read_only=True)
    
    class Meta:
        model = PaymentTransaction
        fields = (
            'id', 'order', 'provider', 'amount', 'currency', 'status',
            'provider_payment_id', 'provider_reference', 'checkout_url',
            'paid_at', 'created_at', 'updated_at', 'checkout_state', 'retry_after'
        )
        read_only_fields = ('id', 'created_at', 'updated_at', 'paid_at')

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        status_val = ret.get('status')
        state_val = getattr(instance, 'checkout_state', 'idle')
        if status_val != 'pending' or state_val != 'ready':
            ret['checkout_url'] = None
        return ret


class ActiveTransactionSerializer(serializers.ModelSerializer):
    can_continue = serializers.BooleanField(read_only=True)
    can_retry = serializers.BooleanField(read_only=True)
    is_initializing = serializers.BooleanField(read_only=True)
    retry_after = serializers.IntegerField(source='checkout_retry_after', read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = (
            'id', 'order', 'provider', 'amount', 'currency', 'status',
            'provider_payment_id', 'provider_reference', 'checkout_url',
            'paid_at', 'created_at', 'updated_at',
            'can_continue', 'can_retry', 'is_initializing', 'checkout_state', 'retry_after'
        )

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if not getattr(instance, 'can_continue', False):
            ret['checkout_url'] = None
        return ret


class CreatePaymentResponseSerializer(serializers.Serializer):
    """Response serializer for checkout creation endpoint - includes all immutable snapshots."""
    transaction_id = serializers.UUIDField(source='id')
    status = serializers.CharField()
    checkout_state = serializers.CharField()
    checkout_url = serializers.URLField(allow_null=True, required=False)
    provider = serializers.CharField()
    # KZT original amounts
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    # Provider conversion snapshot
    provider_amount = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True, required=False)
    provider_currency = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    conversion_rate = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True, required=False)
    conversion_source = serializers.CharField(allow_null=True, required=False, allow_blank=True)


class PaymentStatusResponseSerializer(serializers.Serializer):
    """Response serializer for checking order payment status"""
    order_id = serializers.IntegerField()
    order_payment_status = serializers.CharField()
    latest_transaction = PaymentTransactionSerializer(allow_null=True)
    active_transaction = ActiveTransactionSerializer(allow_null=True)
    active_provider = serializers.CharField()
    provider_mode = serializers.CharField()
    provider_available = serializers.BooleanField()

