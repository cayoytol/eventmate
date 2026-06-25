from rest_framework import serializers
from .models import Plan, Subscription, PromoCode
from apps.payments.models import Payment


class PlanSerializer(serializers.ModelSerializer):
    """Serializer for Plan with i18n support"""
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    entitlements = serializers.SerializerMethodField()
    active = serializers.BooleanField(source='is_active')
    recommended = serializers.BooleanField(source='is_recommended')
    billing_period = serializers.SerializerMethodField()
    
    class Meta:
        model = Plan
        fields = (
            'id', 'code', 'name', 'name_ru', 'name_en', 'name_kz',
            'description', 'description_ru', 'description_en', 'description_kz',
            'price', 'currency', 'duration_days', 'billing_period',
            'entitlements', 'limits_json', 'active', 'is_active', 'recommended', 'is_recommended', 'sort_order'
        )
        
    def get_name(self, obj):
        request = self.context.get('request')
        lang = 'ru'
        if request:
            lang = request.META.get('HTTP_ACCEPT_LANGUAGE', 'ru')[:2].lower()
        if lang == 'en':
            return obj.name_en or obj.name_ru
        elif lang == 'kz':
            return obj.name_kz or obj.name_ru
        return obj.name_ru

    def get_description(self, obj):
        request = self.context.get('request')
        lang = 'ru'
        if request:
            lang = request.META.get('HTTP_ACCEPT_LANGUAGE', 'ru')[:2].lower()
        if lang == 'en':
            return obj.description_en or obj.description_ru
        elif lang == 'kz':
            return obj.description_kz or obj.description_ru
        return obj.description_ru

    def get_price(self, obj):
        from decimal import Decimal
        return f"{Decimal(obj.price):.2f}"

    def get_entitlements(self, obj):
        limits = obj.limits_json or {}
        return {
            "max_active_services": int(limits.get("max_active_services", limits.get("max_services", 3))),
            "max_portfolio_items": int(limits.get("max_portfolio_items", 10)),
            "analytics": bool(limits.get("analytics", False)),
            "ai_features": bool(limits.get("ai_features", False)),
            "featured_placement": bool(limits.get("featured_placement", False)),
            "offers_per_month": int(limits.get("offers_per_month", 10)),
        }

    def get_billing_period(self, obj):
        return f"{obj.duration_days} days"


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for Subscription with nested plan"""
    plan = PlanSerializer(read_only=True)
    provider = serializers.PrimaryKeyRelatedField(source='provider_profile', read_only=True)
    starts_at = serializers.DateTimeField(source='start_date')
    ends_at = serializers.DateTimeField(source='end_date')
    remaining_days = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)  # Legacy compatibility
    is_currently_active = serializers.BooleanField(read_only=True)  # Legacy compatibility
    is_fallback = serializers.BooleanField(default=False, read_only=True)
    auto_renew = serializers.SerializerMethodField()
    effective_status = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = (
            'id', 'provider', 'plan', 'status', 'effective_status', 'starts_at', 'ends_at',
            'cancelled_at', 'auto_renew', 'remaining_days', 'is_active', 'is_currently_active', 'is_fallback', 'created_at'
        )

    def get_remaining_days(self, obj):
        from django.utils import timezone
        now = timezone.now()
        if not obj.end_date:
            return 0
        if obj.end_date <= now:
            return 0
        diff = obj.end_date - now
        return max(0, diff.days)

    def get_auto_renew(self, obj):
        return obj.cancelled_at is None

    def get_effective_status(self, obj):
        from django.utils import timezone
        now = timezone.now()
        
        if not obj.start_date or not obj.end_date:
            return 'pending'
            
        if obj.start_date > now:
            return 'pending'
            
        if obj.status == 'active':
            if obj.end_date <= now:
                return 'expired'
            return 'active'
            
        if obj.status == 'cancelled':
            if obj.end_date <= now:
                return 'expired'
            return 'cancelled_active'
            
        if obj.status == 'expired' or obj.end_date <= now:
            return 'expired'
            
        return obj.status


class SubscribeSerializer(serializers.Serializer):
    """Input serializer for creating subscription"""
    plan_id = serializers.IntegerField()
    promo_code = serializers.CharField(required=False, allow_blank=True)
    
    def validate_plan_id(self, value):
        try:
            plan = Plan.objects.get(id=value, is_active=True)
        except Plan.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive plan")
        return value


class PromoCodeSerializer(serializers.ModelSerializer):
    """Serializer for PromoCode model"""
    is_valid = serializers.SerializerMethodField()
    discount_amount = serializers.SerializerMethodField()
    discount_percent = serializers.SerializerMethodField()

    class Meta:
        model = PromoCode
        fields = (
            'id', 'code', 'discount_percent', 'discount_type', 'discount_amount',
            'max_uses', 'used_count', 'starts_at', 'expires_at', 'is_active', 'is_valid', 'created_at'
        )

    def get_is_valid(self, obj):
        from django.utils import timezone
        if not obj.is_active:
            return False
        if obj.used_count >= obj.max_uses:
            return False
        now = timezone.now()
        if obj.starts_at and obj.starts_at > now:
            return False
        if obj.expires_at and obj.expires_at < now:
            return False
        return True

    def get_discount_amount(self, obj):
        from decimal import Decimal
        if obj.discount_amount is not None:
            return f"{Decimal(obj.discount_amount):.2f}"
        return "0.00"

    def get_discount_percent(self, obj):
        if obj.discount_type == 'percentage' and obj.discount_amount is not None:
            return int(obj.discount_amount)
        return obj.discount_percent or 0


class PromoCodeValidationSerializer(serializers.Serializer):
    """Serializer for validating a promo code input"""
    code = serializers.CharField(max_length=50)
    plan_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        from django.utils import timezone
        code_val = attrs.get('code', '').strip()
        plan_id_val = attrs.get('plan_id')
        
        try:
            promo = PromoCode.objects.get(code__iexact=code_val)
        except PromoCode.DoesNotExist:
            raise serializers.ValidationError({"code": "Invalid promo code"})
            
        if not promo.is_active:
            raise serializers.ValidationError({"code": "Promo code is inactive"})
            
        now = timezone.now()
        if promo.starts_at and promo.starts_at > now:
            raise serializers.ValidationError({"code": "Promo code is not active yet"})
            
        if promo.expires_at and promo.expires_at < now:
            raise serializers.ValidationError({"code": "Promo code has expired"})
            
        if promo.used_count >= promo.max_uses:
            raise serializers.ValidationError({"code": "Promo code has been used up"})
            
        if plan_id_val is not None:
            try:
                plan = Plan.objects.get(id=plan_id_val, is_active=True)
            except Plan.DoesNotExist:
                raise serializers.ValidationError({"plan_id": "Invalid or inactive plan"})
                
            if plan.code == 'free':
                if not promo.eligible_plans.filter(id=plan.id).exists():
                    raise serializers.ValidationError({"code": "Promo code cannot be applied to the Free plan"})
            
            if promo.eligible_plans.exists() and not promo.eligible_plans.filter(id=plan.id).exists():
                raise serializers.ValidationError({"code": "Promo code is not eligible for this plan"})
                
        attrs['promo'] = promo
        return attrs


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    plan_name = serializers.SerializerMethodField()
    original_amount = serializers.SerializerMethodField()
    discount_amount = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    subscription = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Payment
        fields = (
            'id', 'amount', 'original_amount', 'discount_amount', 'currency',
            'status', 'checkout_state', 'checkout_url', 'checkout_expires_at',
            'plan_code_snapshot', 'plan_duration_days_snapshot', 'plan_name',
            'plan_name_ru_snapshot', 'plan_name_en_snapshot', 'plan_name_kz_snapshot',
            'promo_code_snapshot', 'provider', 'provider_payment_id', 'provider_reference',
            'provider_amount', 'provider_currency', 'conversion_rate', 'conversion_source',
            'subscription', 'created_at', 'paid_at', 'updated_at'
        )

    def get_plan_name(self, obj):
        request = self.context.get('request')
        lang = 'ru'
        if request:
            lang = request.META.get('HTTP_ACCEPT_LANGUAGE', 'ru')[:2].lower()
        if lang == 'en':
            return obj.plan_name_en_snapshot or obj.plan_name_ru_snapshot
        elif lang == 'kz':
            return obj.plan_name_kz_snapshot or obj.plan_name_ru_snapshot
        return obj.plan_name_ru_snapshot

    def get_original_amount(self, obj):
        if obj.original_amount is not None:
            return f"{obj.original_amount:.2f}"
        return None

    def get_discount_amount(self, obj):
        if obj.discount_amount is not None:
            return f"{obj.discount_amount:.2f}"
        return None

    def get_amount(self, obj):
        if obj.amount is not None:
            return f"{obj.amount:.2f}"
        return None


class SubscriptionCheckoutSerializer(serializers.Serializer):
    plan_code = serializers.CharField(max_length=50)
    promo_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_plan_code(self, value):
        try:
            plan = Plan.objects.get(code=value, is_active=True)
        except Plan.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive plan")
        if plan.code == 'free':
            raise serializers.ValidationError("Free plan cannot be checked out via transactions")
        return value


class SubscriptionPaymentStatusSerializer(SubscriptionPaymentSerializer):
    class Meta(SubscriptionPaymentSerializer.Meta):
        pass


class SubscriptionPaymentHistorySerializer(SubscriptionPaymentSerializer):
    class Meta(SubscriptionPaymentSerializer.Meta):
        pass

