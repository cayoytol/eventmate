from rest_framework import views, permissions, status, generics
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.conf import settings
from django.contrib.auth import get_user_model
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from apps.core.media import safe_delete_image

from .serializers import (
    UserSerializer, RegisterSerializer, LoginSerializer,
    EmailVerifySerializer, PhoneSendOtpSerializer, PhoneVerifyOtpSerializer
)
from .utils import (
    generate_email_token, verify_email_token, send_mock_email,
    generate_phone_otp, verify_mock_otp, send_mock_otp_sms
)

User = get_user_model()

# --- Auth JWT Views ---

class CookieTokenObtainPairView(TokenObtainPairView):
    def finalize_response(self, request, response, *args, **kwargs):
        # Only set cookie on successful login (200 OK)
        # On error (400, 401), response.data['refresh'] may contain ErrorDetail with Unicode text
        if response.status_code == 200 and response.data.get('refresh'):
            refresh_value = response.data['refresh']
            
            # Double-check: refresh token must be a string (JWT), not ErrorDetail
            if isinstance(refresh_value, str):
                cookie_max_age = 3600 * 24 * 14 # 14 days
                response.set_cookie(
                    settings.SIMPLE_JWT['AUTH_COOKIE'],
                    refresh_value,
                    max_age=cookie_max_age,
                    httponly=settings.SIMPLE_JWT['AUTH_COOKIE_HTTP_ONLY'],
                    samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE'],
                    secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
                )
                del response.data['refresh']
        return super().finalize_response(request, response, *args, **kwargs)

class CookieTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get(settings.SIMPLE_JWT['AUTH_COOKIE'])
        if refresh_token:
            if isinstance(request.data, dict):
                request.data['refresh'] = refresh_token
            else:
                try:
                    request.data._mutable = True
                    request.data['refresh'] = refresh_token
                except AttributeError:
                    data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
                    data['refresh'] = refresh_token
                    request._full_data = data
        return super().post(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        # Only set cookie on successful refresh (200 OK)
        # On error (400, 401), response.data['refresh'] may contain ErrorDetail with Unicode text
        if response.status_code == 200 and response.data.get('refresh'):
            refresh_value = response.data['refresh']
            
            # Double-check: refresh token must be a string (JWT), not ErrorDetail
            if isinstance(refresh_value, str):
                cookie_max_age = 3600 * 24 * 14
                response.set_cookie(
                    settings.SIMPLE_JWT['AUTH_COOKIE'],
                    refresh_value,
                    max_age=cookie_max_age,
                    httponly=settings.SIMPLE_JWT['AUTH_COOKIE_HTTP_ONLY'],
                    samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE'],
                    secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
                )
                del response.data['refresh']
        
        # DEBUG: Check all headers/cookies for non-ASCII characters
        if settings.DEBUG:
            import logging
            logger = logging.getLogger(__name__)
            
            logger.debug(f"🔍 [AUTH REFRESH] Response status: {response.status_code}")
            
            # Check all response headers
            for header_name, header_value in response.items():
                try:
                    # HTTP headers must be ASCII (Latin-1)
                    str(header_value).encode('ascii')
                except (UnicodeEncodeError, AttributeError) as e:
                    logger.error(f"❌ Header '{header_name}' contains non-ASCII: {header_value!r}")
                    logger.error(f"   Error: {e}")
            
            # Check all cookies
            if hasattr(response, 'cookies'):
                for cookie_name, cookie_obj in response.cookies.items():
                    try:
                        # Check cookie name
                        cookie_name.encode('ascii')
                        # Check cookie value
                        cookie_obj.value.encode('ascii')
                        logger.debug(f"✅ Cookie '{cookie_name}' is ASCII-safe")
                    except (UnicodeEncodeError, AttributeError) as e:
                        logger.error(f"❌ Cookie '{cookie_name}' contains non-ASCII")
                        logger.error(f"   Value: {cookie_obj.value!r}")
                        logger.error(f"   Error: {e}")
            
            logger.debug("✅ [AUTH REFRESH] All headers/cookies checked")
        
        return super().finalize_response(request, response, *args, **kwargs)

class LogoutView(views.APIView):
    def post(self, request):
        response = Response({"detail": "Successfully logged out"}, status=status.HTTP_200_OK)
        response.delete_cookie(settings.SIMPLE_JWT['AUTH_COOKIE'])
        return response

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

# --- Email Verification ---

class EmailSendVerifyView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.email_verified:
            return Response({"detail": "Email already verified"}, status=status.HTTP_400_BAD_REQUEST)
        
        token = generate_email_token(user)
        send_mock_email(user, token)
        return Response({"detail": "Verification email sent"}, status=status.HTTP_200_OK)

class EmailVerifyView(views.APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(manual_parameters=[
        openapi.Parameter('token', openapi.IN_QUERY, description="Verification Token", type=openapi.TYPE_STRING)
    ])
    def get(self, request):
        token = request.query_params.get('token')
        if not token:
            return Response({"detail": "Token required"}, status=status.HTTP_400_BAD_REQUEST)
            
        user_id = verify_email_token(token)
        if not user_id:
            return Response({"detail": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            user = User.objects.get(id=user_id)
            user.email_verified = True
            user.save()
            return Response({"detail": "Email successfully verified"}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

# --- Phone OTP ---

class PhoneSendOtpView(views.APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PhoneSendOtpSerializer

    @swagger_auto_schema(request_body=PhoneSendOtpSerializer)
    def post(self, request):
        serializer = PhoneSendOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']
        
        code = generate_phone_otp(phone)
        send_mock_otp_sms(phone, code)
        
        response_data = {"detail": "OTP sent"}
        
        if settings.DEBUG:
            response_data["debug_code"] = code
            
        return Response(response_data, status=status.HTTP_200_OK)

class PhoneVerifyOtpView(views.APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PhoneVerifyOtpSerializer

    @swagger_auto_schema(request_body=PhoneVerifyOtpSerializer)
    def post(self, request):
        serializer = PhoneVerifyOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']
        code = serializer.validated_data['code']
        
        if verify_mock_otp(phone, code):
            if request.user.is_authenticated:
                request.user.phone = phone
                request.user.phone_verified = True
                request.user.save()
                return Response({"detail": "Phone verified and linked"}, status=status.HTTP_200_OK)
            else:
                 return Response({"detail": "OTP correct"}, status=status.HTTP_200_OK)
        else:
            return Response({"detail": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

from rest_framework import viewsets
from rest_framework.decorators import action
from apps.accounts.serializers import AvailabilitySerializer
from apps.accounts.models import Availability, ProviderProfile

class IsProvider(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'provider' and hasattr(request.user, 'provider_profile')

class AvailabilityViewSet(viewsets.ModelViewSet):
    permission_classes = [IsProvider]
    serializer_class = AvailabilitySerializer
    
    def get_queryset(self):
        qs = Availability.objects.filter(provider__user=self.request.user).order_by('start_at')
        
        # Filter by range
        start_date = self.request.query_params.get('from')
        end_date = self.request.query_params.get('to')
        
        if start_date:
            qs = qs.filter(end_at__date__gte=start_date)
        if end_date:
            qs = qs.filter(start_at__date__lte=end_date)
            
        return qs
    
    def perform_create(self, serializer):
        serializer.save(provider=self.request.user.provider_profile, status='blocked')
        
    @action(detail=False, methods=['get'])
    def my(self, request):
        """GET /api/v1/availability/my/"""
        return self.list(request)


class ProviderProfilePublicView(generics.RetrieveAPIView):
    from apps.accounts.models import ProviderProfile
    from apps.accounts.serializers import ProviderPublicProfileSerializer
    queryset = ProviderProfile.objects.all()
    serializer_class = ProviderPublicProfileSerializer
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        from django.http import Http404
        obj = super().get_object()
        user = self.request.user
        if obj.is_blocked and not (user and user.is_authenticated and user.is_staff):
            raise Http404("Provider profile not found.")
        return obj

class ProviderBlockView(views.APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        from django.shortcuts import get_object_or_404
        from django.db import transaction
        from apps.accounts.models import ProviderProfile
        from apps.audit.utils import log_action, get_client_ip

        with transaction.atomic():
            profile = get_object_or_404(ProviderProfile, pk=pk)
            if not profile.is_blocked:
                profile.is_blocked = True
                profile.save(update_fields=['is_blocked'])
                log_action(
                    actor=request.user,
                    action='PROVIDER_BLOCKED',
                    target_type='provider',
                    target_id=profile.id,
                    ip_address=get_client_ip(request),
                    details_json={"provider_email": profile.user.email}
                )
        return Response({"status": "blocked", "is_blocked": True}, status=status.HTTP_200_OK)

class ProviderUnblockView(views.APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        from django.shortcuts import get_object_or_404
        from django.db import transaction
        from apps.accounts.models import ProviderProfile
        from apps.audit.utils import log_action, get_client_ip

        with transaction.atomic():
            profile = get_object_or_404(ProviderProfile, pk=pk)
            if profile.is_blocked:
                profile.is_blocked = False
                profile.save(update_fields=['is_blocked'])
                log_action(
                    actor=request.user,
                    action='PROVIDER_UNBLOCKED',
                    target_type='provider',
                    target_id=profile.id,
                    ip_address=get_client_ip(request),
                    details_json={"provider_email": profile.user.email}
                )
        return Response({"status": "unblocked", "is_blocked": False}, status=status.HTTP_200_OK)


from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.throttling import ScopedRateThrottle
from apps.accounts.permissions import IsNotBlockedProvider

class UserAvatarView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsNotBlockedProvider]
    parser_classes = [MultiPartParser, FormParser]

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = "media_upload"
            return [ScopedRateThrottle()]
        return []

    def post(self, request, *args, **kwargs):
        user = request.user
        if user.role != 'provider':
            return Response(
                {"detail": "Only providers are allowed to modify their avatar."},
                status=status.HTTP_403_FORBIDDEN
            )

        if 'avatar' not in request.FILES:
            return Response(
                {"detail": "No avatar file was provided in the request."},
                status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_file = request.FILES['avatar']

        # Reuse shared image processor
        from django.core.exceptions import ValidationError as DjangoValidationError
        from apps.core.media import validate_and_process_image, generate_image_storage_name
        
        try:
            processed = validate_and_process_image(uploaded_file)
        except DjangoValidationError as e:
            msg = e.messages[0] if hasattr(e, 'messages') else str(e)
            if isinstance(msg, list):
                msg = msg[0]
            return Response(
                {"detail": msg},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate unique storage path
        try:
            final_name = generate_image_storage_name(
                prefix="avatars",
                owner_id=user.pk,
                extension=processed.extension,
            )
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        storage = user.avatar.storage
        try:
            saved_name = storage.save(final_name, processed.content)
        except Exception:
            return Response(
                {"detail": "Failed to save avatar image to storage."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        from django.db import transaction

        try:
            with transaction.atomic():
                locked_user = User.objects.select_for_update().get(pk=user.pk)
                if locked_user.role != 'provider':
                    raise ValueError("User role is not provider.")

                old_name = locked_user.avatar.name if locked_user.avatar else None

                locked_user.avatar.name = saved_name
                locked_user.save(update_fields=["avatar"])
        except Exception:
            # Clean up newly saved file on failure
            try:
                if storage.exists(saved_name):
                    storage.delete(saved_name)
            except Exception:
                pass
            import logging
            logging.getLogger(__name__).error("[Avatar Upload] Database update failed. Rolled back file save.")
            return Response(
                {"detail": "Failed to save avatar to database."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        if old_name and old_name != saved_name:
            def delete_old():
                safe_delete_image(storage, old_name)
            transaction.on_commit(delete_old)

        serializer = UserSerializer(locked_user, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        user = request.user
        if user.role != 'provider':
            return Response(
                {"detail": "Only providers are allowed to modify their avatar."},
                status=status.HTTP_403_FORBIDDEN
            )

        from django.db import transaction

        try:
            with transaction.atomic():
                locked_user = User.objects.select_for_update().get(pk=user.pk)
                if locked_user.role != 'provider':
                    raise ValueError("User role is not provider.")

                old_name = locked_user.avatar.name if locked_user.avatar else None
                storage = locked_user.avatar.storage

                if old_name:
                    locked_user.avatar.name = None
                    locked_user.save(update_fields=["avatar"])
        except Exception:
            return Response(
                {"detail": "Failed to delete avatar from database."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        if old_name:
            def delete_old():
                safe_delete_image(storage, old_name)
            transaction.on_commit(delete_old)

        return Response(status=status.HTTP_204_NO_CONTENT)


