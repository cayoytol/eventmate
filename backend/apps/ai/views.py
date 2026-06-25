from django.conf import settings
from rest_framework import views, permissions, status
from rest_framework.response import Response
from .serializers import RequestAssistantSerializer, OfferAssistantSerializer
from . import services

class IsClientRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'client'

class IsProviderRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'provider'

class RequestAssistantView(views.APIView):
    permission_classes = [IsClientRole]

    def post(self, request):
        ai_key = getattr(settings, 'AI_API_KEY', '') or ''
        ai_url = getattr(settings, 'AI_API_URL', '') or ''
        if not ai_key or not ai_url:
            return Response(
                {"code": "ai_not_configured", "detail": "AI service is not configured."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = RequestAssistantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        suggested_text, source = services.generate_request_suggestion(
            category=data.get('category', ''),
            city=data.get('city', ''),
            event_date=data.get('event_date', ''),
            budget=data.get('budget', ''),
            draft=data.get('draft', ''),
            locale=data.get('locale', 'ru')
        )

        return Response({
            "suggested_text": suggested_text,
            "source": source
        }, status=status.HTTP_200_OK)

class OfferAssistantView(views.APIView):
    permission_classes = [IsProviderRole]

    def post(self, request):
        ai_key = getattr(settings, 'AI_API_KEY', '') or ''
        ai_url = getattr(settings, 'AI_API_URL', '') or ''
        if not ai_key or not ai_url:
            return Response(
                {"code": "ai_not_configured", "detail": "AI service is not configured."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Enforce subscription entitlement checks for providers (Task 4)
        from apps.billing.services.entitlements import has_entitlement
        try:
            provider_profile = request.user.provider_profile
        except Exception:
            return Response(
                {"code": "subscription_required", "detail": "Provider profile not found."},
                status=status.HTTP_403_FORBIDDEN
            )

        if not has_entitlement(provider_profile, "ai_features"):
            return Response(
                {"code": "subscription_required", "detail": "AI features require an active Pro or Enterprise subscription."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = OfferAssistantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        suggested_letter, source = services.generate_offer_suggestion(
            request_description=data.get('request_description'),
            service_title=data.get('service_title', ''),
            price=data.get('price', ''),
            locale=data.get('locale', 'ru')
        )

        return Response({
            "suggested_letter": suggested_letter,
            "source": source
        }, status=status.HTTP_200_OK)
