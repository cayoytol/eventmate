from rest_framework import viewsets, permissions, status, mixins, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend
import jwt
import uuid
import hashlib

from .models import EventRequest, Offer, Order, Review
from .serializers import (
    EventRequestSerializer, EventRequestListSerializer,
    OfferSerializer, EmptySerializer,
    OrderListSerializer, OrderDetailSerializer, OrderActionSerializer,
    OrderQRScanSerializer
)
from .review_serializers import ReviewSerializer

from .permissions import IsRequestClient, IsOfferProvider, IsProvider
from apps.accounts.permissions import IsNotBlockedProvider
from apps.catalog.serializers import ServiceDetailSerializer
from apps.notifications.services import create_notification
from apps.notifications.models import Notification as NotificationModel
import logging
from .utils import get_order_qr_capabilities

logger = logging.getLogger(__name__)

def safe_create_notification(user, title, message, n_type, metadata=None):
    try:
        return create_notification(
            user=user,
            title=title,
            message=message,
            n_type=n_type,
            metadata=metadata
        )
    except Exception as e:
        logger.exception("Failed to create notification safely")
        return None


class EventRequestViewSet(mixins.CreateModelMixin,
                          mixins.RetrieveModelMixin,
                          mixins.ListModelMixin,
                          viewsets.GenericViewSet):
    """
    API для Заявок.
    """
    queryset = EventRequest.objects.all().select_related('category', 'client')
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from django.db.models import Count
        user = self.request.user
        
        # Provider: see targeted requests + general requests in their categories
        if hasattr(user, 'role') and user.role == 'provider':
            try:
                provider_profile = user.provider_profile
                
                # Get categories of provider's services
                from apps.catalog.models import Service
                my_categories = Service.objects.filter(
                    provider=provider_profile
                ).values_list('category_id', flat=True).distinct()
                
                # Targeted to me OR (general AND in my category)
                qs = self.queryset.filter(
                    Q(target_provider=provider_profile) |  # Targeted to me
                    Q(target_provider__isnull=True, category_id__in=my_categories)  # General in my categories
                )
            except Exception:
                # Provider without profile sees nothing
                qs = self.queryset.none()
        else:
            # Client: see only own requests
            qs = self.queryset.filter(client=user)
        
        # For list view, annotate with offers count
        if self.action == 'list' or self.action == 'my':
            qs = qs.annotate(offers_count=Count('offers'))
            
        return qs.order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'list' or self.action == 'my':
            return EventRequestListSerializer
        return EventRequestSerializer

    def perform_create(self, serializer):
        from rest_framework.exceptions import PermissionDenied
        
        # Enforce that only clients can create requests
        if getattr(self.request.user, 'role', None) != 'client':
            raise PermissionDenied("Only clients can create requests.")

        instance = serializer.save(client=self.request.user, status=EventRequest.Status.OFFERS)
        if instance.target_provider:
            safe_create_notification(
                user=instance.target_provider.user,
                title="Новая заявка",
                message=f"Вы получили персональный запрос: {instance.title or 'Без названия'}",
                n_type=NotificationModel.NotificationType.NEW_REQUEST,
                metadata={
                    'request_id': instance.id,
                    'service_id': instance.target_service.id if instance.target_service else None
                }
            )
        else:
            # TODO: General requests notification to matching providers
            pass

    @action(detail=False, methods=['get'])
    def my(self, request):
        return self.list(request)

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated, IsRequestClient])
    def offers(self, request, pk=None):
        event_request = self.get_object()
        offers = Offer.objects.filter(request=event_request).select_related('service', 'provider_profile__user')
        serializer = OfferSerializer(offers, many=True)
        return Response(serializer.data)


class OfferViewSet(mixins.CreateModelMixin,
                   viewsets.GenericViewSet):
    """
    API для Офферов (Создание + Actions).
    """
    queryset = Offer.objects.all()
    
    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated(), IsProvider(), IsNotBlockedProvider()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action in ['withdraw', 'accept', 'reject']:
            return EmptySerializer
        return OfferSerializer


    def perform_create(self, serializer):
        # Check billing limit before creating offer
        from apps.billing import services as billing_services
        from apps.billing.exceptions import PlanLimitReached
        
        provider_profile = self.request.user.provider_profile
        if not billing_services.check_offer_limit(provider_profile):
            raise PlanLimitReached("offers_per_month")
        
        serializer.save(provider_profile=provider_profile)
        
        # Trigger: NEW_OFFER (notify client)
        offer = serializer.instance
        safe_create_notification(
            user=offer.request.client,
            title="Новое предложение",
            message=f"Получено новое предложение по вашей заявке: {offer.request.title or 'Без названия'}",
            n_type=NotificationModel.NotificationType.NEW_OFFER,
            metadata={
                'offer_id': offer.id,
                'request_id': offer.request.id,
                'provider_email': provider_profile.user.email
            }
        )

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated, IsProvider])
    def my(self, request):
        """Get provider's own offers"""
        provider_profile = request.user.provider_profile
        offers = Offer.objects.filter(
            provider_profile=provider_profile
        ).select_related('request', 'service', 'provider_profile__user').order_by('-created_at')
        
        serializer = OfferSerializer(offers, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='by-request/(?P<request_id>[^/.]+)', permission_classes=[permissions.IsAuthenticated])
    def by_request(self, request, request_id=None):
        """Get offers for a specific request (client only)"""
        try:
            event_request = EventRequest.objects.get(id=request_id)
        except (EventRequest.DoesNotExist, ValueError):
            return Response({"detail": "Request not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Only client who owns the request can view offers
        if event_request.client_id != request.user.id:
            return Response(
                {"detail": "You can only view offers for your own requests"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        offers = Offer.objects.filter(
            request=event_request
        ).select_related('service', 'provider_profile__user').order_by('-created_at')
        
        serializer = OfferSerializer(offers, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsOfferProvider])
    def withdraw(self, request, pk=None):
        offer = self.get_object()
        
        if offer.status != Offer.Status.SENT:
            return Response({"detail": "Cannot withdraw offer that is not SENT."}, status=status.HTTP_400_BAD_REQUEST)
            
        offer.status = Offer.Status.WITHDRAWN
        offer.save()
        return Response({"status": "withdrawn"})

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """
        Accept an offer atomically:
        - Lock request with select_for_update()
        - Check for double-accept
        - Accept winner, reject all other SENT offers (excluding winner explicitly)
        - Create Order
        - Notify winner and all losers
        """
        with transaction.atomic():
            try:
                # 1. Fetch request ID without locking to lock in hierarchical order (EventRequest first)
                offer_preview = Offer.objects.select_related('request').get(pk=pk)
                request_id = offer_preview.request.id
                
                # 2. Lock the parent EventRequest row first
                event_request = EventRequest.objects.select_for_update().get(pk=request_id)
                
                # 3. Lock the Offer row second
                offer = Offer.objects.select_for_update().select_related('service').get(pk=pk)
            except (Offer.DoesNotExist, EventRequest.DoesNotExist):
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)


            # Permission: only client who owns request can accept
            if event_request.client != request.user:
                return Response(
                    {"detail": "You do not have permission to accept this offer."},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Validation: offer must be SENT
            if offer.status != Offer.Status.SENT:
                return Response(
                    {"detail": "Offer is not in SENT status."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validation: request must be in OFFERS status
            if event_request.status != EventRequest.Status.OFFERS:
                return Response(
                    {"detail": "Request must be in OFFERS status to accept."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Double-accept protection: check if another offer already accepted
            already_accepted = Offer.objects.filter(
                request=event_request,
                status=Offer.Status.ACCEPTED
            ).exclude(id=offer.id).exists()
            
            if already_accepted:
                return Response(
                    {"detail": "Another offer has already been accepted for this request."},
                    status=status.HTTP_409_CONFLICT
                )

            # ✅ Optimized: collect (offer_id, user_id) BEFORE bulk update
            # This avoids extra query after update
            losers = list(
                Offer.objects.filter(
                    request=event_request,
                    status=Offer.Status.SENT
                ).exclude(id=offer.id)  # ✅ Explicitly exclude winner
                .values_list('id', 'provider_profile__user_id')
            )
            
            # Accept winner
            offer.status = Offer.Status.ACCEPTED
            offer.save(update_fields=['status'])
            
            # Update request status
            event_request.status = EventRequest.Status.CONFIRMED
            event_request.save(update_fields=['status'])
            
            # ✅ Bulk reject: explicitly exclude winner
            # This ensures winner is never touched even if status changed between queries
            Offer.objects.filter(
                request=event_request,
                status=Offer.Status.SENT
            ).exclude(id=offer.id).update(status=Offer.Status.REJECTED)
            
            # Create Order snapshot
            service_data = ServiceDetailSerializer(offer.service, context={'request': request}).data
            
            # Add event_date from request to snapshot
            service_data['event_date'] = offer.request.event_date.isoformat()
            
            order = Order.objects.create(
                offer=offer,
                client=request.user,
                provider_profile=offer.provider_profile,
                price_agreed=offer.price,
                service_snapshot=service_data
            )
            
            # Notify winner (accepted provider)
            safe_create_notification(
                user=offer.provider_profile.user,
                title="Предложение принято",
                message=f"Ваше предложение по заявке '{offer.request.title or 'Без названия'}' принято! Создан заказ #{order.id}.",
                n_type=NotificationModel.NotificationType.OFFER_ACCEPTED,
                metadata={
                    'order_id': order.id,
                    'offer_id': offer.id,
                    'client_email': request.user.email
                }
            )
            
            # ✅ Notify losers (rejected providers) - optimized bulk fetch
            if losers:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                
                # Collect unique user IDs
                loser_user_ids = {user_id for _, user_id in losers}
                
                # ✅ Single query: fetch all users at once
                user_map = User.objects.in_bulk(loser_user_ids)
                
                # Create notifications using fetched users (no extra queries)
                for loser_offer_id, loser_user_id in losers:
                    loser_user = user_map.get(loser_user_id)
                    if loser_user:  # Skip if user deleted between query and notification
                        safe_create_notification(
                            user=loser_user,
                            title="Предложение отклонено",
                            message=f"Клиент выбрал другого исполнителя по заявке '{event_request.title or 'Без названия'}'",
                            n_type=NotificationModel.NotificationType.OFFER_REJECTED,
                            metadata={
                                'offer_id': loser_offer_id,
                                'request_id': event_request.id,
                                'reason': 'client_selected_another'
                            }
                        )
            
            return Response({"status": "accepted", "order_created": True})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        offer = self.get_object()
        event_request = offer.request

        if event_request.client != request.user:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
            
        if offer.status != Offer.Status.SENT:
             return Response({"detail": "Offer is not in SENT status."}, status=status.HTTP_400_BAD_REQUEST)
             
        if event_request.status in [EventRequest.Status.CONFIRMED, EventRequest.Status.CANCELLED]:
             return Response({"detail": "Request is closed."}, status=status.HTTP_400_BAD_REQUEST)

        offer.status = Offer.Status.REJECTED
        offer.save()
        return Response({"status": "rejected"})


class OrderViewSet(mixins.ListModelMixin,
                   mixins.RetrieveModelMixin,
                   viewsets.GenericViewSet):
    """
    API для Заказов.
    """
    queryset = Order.objects.all().select_related('client', 'provider_profile__user')
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        """
        Filter orders based on user role:
        - Provider: sees orders where they are the provider
        - Client: sees orders where they are the client
        - Staff: sees all orders
        """
        user = self.request.user
        
        # Provider sees their orders
        if user.role == 'provider':
            if not hasattr(user, 'provider_profile') or user.provider_profile is None:
                return Order.objects.none()
            return self.queryset.filter(provider_profile=user.provider_profile)
        
        # Client sees their orders
        if user.role == 'client':
            return self.queryset.filter(client=user)
        
        # Staff sees all
        if user.is_staff:
            return self.queryset.all()
        
        # Default: no orders
        return Order.objects.none()

    def get_serializer_class(self):
        if self.action in ['cancel', 'dispute']:
            return OrderActionSerializer
        if self.action in ['check_in', 'complete']:
            return OrderQRScanSerializer
            
        if self.action == 'retrieve':
            return OrderDetailSerializer
        return OrderListSerializer

    def _verify_qr_token(self, token, order_id, expected_type):
        """
        Helper to verify QR JWT token.
        Returns (payload, error_code, error_detail)
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return None, "qr_token_expired", "Token expired"
        except jwt.InvalidTokenError:
            return None, "invalid_qr_token", "Invalid token"

        if payload.get('order_id') != order_id:
            return None, "qr_token_wrong_order", "Token does not belong to this order"
            
        if payload.get('type') != expected_type:
            return None, "qr_token_wrong_type", f"Invalid token type (expected {expected_type})"
             
        return payload, None, None

    @action(detail=True, methods=['get'], url_path="qr-code")
    def qr_code(self, request, pk=None):
        """Generate QR Token (Client only)"""
        # Security: return 404 for both non-existent and unauthorized access
        # to prevent order ID enumeration attacks
        try:
            order = Order.objects.select_related('client').get(pk=pk)
        except Order.DoesNotExist:
            return Response({"code": "qr_not_available", "detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        
        capabilities = get_order_qr_capabilities(order, request.user)

        # Return 404 (not 403) to hide order existence from non-owners
        if not capabilities.get("is_client_owner"):
            return Response({"code": "qr_not_available", "detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        
        # Payment gating: QR codes require payment
        if order.payment_status != Order.PaymentStatus.PAID:
            return Response(
                {"code": "order_not_paid", "detail": "Payment required to access QR functionality."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        qr_type = request.query_params.get('type')
        if qr_type not in ['start', 'finish']:
            return Response({"code": "invalid_qr_type", "detail": "Invalid type. Use 'start' or 'finish'."}, status=status.HTTP_400_BAD_REQUEST)
            
        # Logic check status
        if qr_type == 'start' and order.status != Order.Status.CONFIRMED:
             return Response({"code": "invalid_order_status", "detail": "Order must be CONFIRMED to generate start QR."}, status=status.HTTP_400_BAD_REQUEST)
             
        if qr_type == 'finish' and order.status != Order.Status.IN_PROGRESS:
             return Response({"code": "invalid_order_status", "detail": "Order must be IN_PROGRESS to generate finish QR."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate Token
        nonce = str(uuid.uuid4())
        exp = timezone.now() + timezone.timedelta(minutes=5)
        
        payload = {
            'order_id': order.id,
            'type': qr_type,
            'nonce': nonce,
            'exp': int(exp.timestamp())  # Must be int for JWT standard
        }
        
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
        
        # Normalize token (handle bytes from older PyJWT versions)
        if isinstance(token, bytes):
            token = token.decode('utf-8')
        
        # Hash with explicit UTF-8 encoding
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        
        # Save Hash (update only the specific field for this QR type)
        if qr_type == 'start':
            order.qr_start_token_hash = token_hash
            order.save(update_fields=['qr_start_token_hash'])
        else:
            order.qr_finish_token_hash = token_hash
            order.save(update_fields=['qr_finish_token_hash'])
        
        return Response({
            "token": token,
            "expires_at": exp.isoformat()
        })

    @action(detail=True, methods=['post'], url_path="actions/check-in")
    def check_in(self, request, pk=None):
        """CONFIRMED -> IN_PROGRESS (Provider scan)"""
        serializer = OrderQRScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']

        with transaction.atomic():
            try:
                order = Order.objects.select_for_update().get(pk=pk)
            except Order.DoesNotExist:
                return Response({"code": "qr_not_available", "detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

            capabilities = get_order_qr_capabilities(order, request.user)
            if not capabilities.get("is_assigned_provider"):
                return Response({"code": "qr_not_available", "detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
            
            # Payment gating: cannot check-in unpaid orders
            if order.payment_status != Order.PaymentStatus.PAID:
                return Response(
                    {"code": "order_not_paid", "detail": "Payment required to access QR functionality."},
                    status=status.HTTP_403_FORBIDDEN
                )

            if order.status != Order.Status.CONFIRMED:
                return Response({"code": "invalid_order_status", "detail": "Order must be CONFIRMED to check-in."}, status=status.HTTP_400_BAD_REQUEST)

            payload, err_code, err_detail = self._verify_qr_token(token, order.id, 'start')
            if err_code:
                return Response({"code": err_code, "detail": err_detail}, status=status.HTTP_400_BAD_REQUEST)

            # Normalize token (handle bytes from older PyJWT versions)
            if isinstance(token, bytes):
                token = token.decode('utf-8')

            # Verify Hash with explicit UTF-8 encoding (must match qr_code logic)
            token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
            if not order.qr_start_token_hash or order.qr_start_token_hash != token_hash:
                return Response({"code": "qr_token_replaced", "detail": "Invalid or expired QR code."}, status=status.HTTP_403_FORBIDDEN)

            order.status = Order.Status.IN_PROGRESS
            order.checkin_at = timezone.now()
            order.qr_start_token_hash = ''  # invalidate
            order.save(update_fields=['status', 'checkin_at', 'qr_start_token_hash'])

            logger.info("QR_SCAN_START success", extra={
                "action": "QR_SCAN_START",
                "order_id": order.id,
                "actor_id": request.user.id,
                "result": "success"
            })

            def notify_client():
                safe_create_notification(
                    user=order.client,
                    title="Исполнитель начал работу",
                    message=f"Исполнитель подтвердил начало работы по заказу #{order.id}.",
                    n_type=NotificationModel.NotificationType.ORDER_COMPLETED,
                    metadata={'order_id': order.id}
                )
            transaction.on_commit(notify_client)

            return Response({'status': 'in_progress', 'checkin_at': order.checkin_at})

    @action(detail=True, methods=['post'], url_path="actions/complete")
    def complete(self, request, pk=None):
        """IN_PROGRESS -> COMPLETED (Provider scan)"""
        serializer = OrderQRScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']

        with transaction.atomic():
            try:
                order = Order.objects.select_for_update().get(pk=pk)
            except Order.DoesNotExist:
                return Response({"code": "qr_not_available", "detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

            capabilities = get_order_qr_capabilities(order, request.user)
            if not capabilities.get("is_assigned_provider"):
                return Response({"code": "qr_not_available", "detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
            
            # Payment gating: cannot complete unpaid orders
            if order.payment_status != Order.PaymentStatus.PAID:
                return Response(
                    {"code": "order_not_paid", "detail": "Payment required to access QR functionality."},
                    status=status.HTTP_403_FORBIDDEN
                )

            if order.status != Order.Status.IN_PROGRESS:
                return Response({"code": "invalid_order_status", "detail": "Order must be IN_PROGRESS to complete."}, status=status.HTTP_400_BAD_REQUEST)

            payload, err_code, err_detail = self._verify_qr_token(token, order.id, 'finish')
            if err_code:
                return Response({"code": err_code, "detail": err_detail}, status=status.HTTP_400_BAD_REQUEST)

            # Normalize token (handle bytes from older PyJWT versions)
            if isinstance(token, bytes):
                token = token.decode('utf-8')

            # Verify Hash with explicit UTF-8 encoding (must match qr_code logic)
            token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
            if not order.qr_finish_token_hash or order.qr_finish_token_hash != token_hash:
                return Response({"code": "qr_token_replaced", "detail": "Invalid or expired QR code."}, status=status.HTTP_403_FORBIDDEN)

            order.status = Order.Status.COMPLETED
            order.completed_at = timezone.now()
            order.qr_finish_token_hash = ''  # invalidate
            order.save(update_fields=['status', 'completed_at', 'qr_finish_token_hash'])

            logger.info("QR_SCAN_FINISH success", extra={
                "action": "QR_SCAN_FINISH",
                "order_id": order.id,
                "actor_id": request.user.id,
                "result": "success"
            })

            def notify_participants():
                safe_create_notification(
                    user=order.provider_profile.user,
                    title="Заказ завершен",
                    message=f"Работа по заказу #{order.id} завершена.",
                    n_type=NotificationModel.NotificationType.ORDER_COMPLETED,
                    metadata={'order_id': order.id}
                )
                safe_create_notification(
                    user=order.client,
                    title="Заказ завершен",
                    message=f"Заказ #{order.id} отмечен как выполненный.",
                    n_type=NotificationModel.NotificationType.ORDER_COMPLETED,
                    metadata={'order_id': order.id}
                )
            transaction.on_commit(notify_participants)

            return Response({'status': 'completed', 'completed_at': order.completed_at})
    
    @action(detail=True, methods=['post'], url_path="actions/mock-pay")
    def mock_pay(self, request, pk=None):
        """
        DEV ONLY: Mock payment endpoint for testing
        Transitions order payment_status from UNPAID -> PAID
        """
        # CRITICAL: DEV-ONLY - block in production or if mock is disabled
        if not settings.DEBUG or not getattr(settings, 'PAYMENT_MOCK_ENABLED', False):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            order = Order.objects.select_for_update().get(pk=pk)
        except Order.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        
        # Permission: Only client (order owner) can pay
        if order.client_id != request.user.id:
            return Response(
                {"detail": "Only the client can pay for this order."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check order status: can only pay CONFIRMED orders
        if order.status != Order.Status.CONFIRMED:
            return Response(
                {"detail": "Can only pay for CONFIRMED orders."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Block payment for closed orders
        if order.status in [Order.Status.CANCELLED, Order.Status.DISPUTED, Order.Status.COMPLETED]:
            return Response(
                {"detail": "Cannot pay for closed orders."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check payment status: must be UNPAID
        if order.payment_status != Order.PaymentStatus.UNPAID:
            return Response(
                {"detail": f"Order is already {order.payment_status}."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update payment status
        order.payment_status = Order.PaymentStatus.PAID
        order.save(update_fields=['payment_status'])
        
        # Trigger: ORDER_PAID (notify provider and client)
        safe_create_notification(
            user=order.provider_profile.user,
            title="Заказ оплачен",
            message=f"Заказ #{order.id} успешно оплачен клиентом.",
            n_type=NotificationModel.NotificationType.ORDER_PAID,
            metadata={'order_id': order.id}
        )
        safe_create_notification(
            user=order.client,
            title="Заказ оплачен",
            message=f"Оплата заказа #{order.id} прошла успешно.",
            n_type=NotificationModel.NotificationType.ORDER_PAID,
            metadata={'order_id': order.id}
        )
        
        return Response({
            "status": "paid",
            "payment_status": order.payment_status,
            "order_id": order.id
        })

    @action(detail=True, methods=['post'], url_path="actions/cancel")
    def cancel(self, request, pk=None):
        """CONFIRMED -> CANCELLED"""
        serializer = OrderActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            try:
                order = Order.objects.select_for_update().get(pk=pk)
            except Order.DoesNotExist:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
            
            is_client = (order.client == request.user)
            is_provider = (hasattr(request.user, 'provider_profile') and order.provider_profile == request.user.provider_profile)
            
            if not (is_client or is_provider):
                return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
                
            if order.status != Order.Status.CONFIRMED:
                return Response({"detail": "Only CONFIRMED orders can be cancelled."}, status=status.HTTP_400_BAD_REQUEST)
            
            order.status = Order.Status.CANCELLED
            order.save()
            return Response({'status': 'cancelled'})
            
    @action(detail=True, methods=['post'], url_path="actions/dispute")
    def dispute(self, request, pk=None):
        """ANY -> DISPUTED"""
        serializer = OrderActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            try:
                order = Order.objects.select_for_update().get(pk=pk)
            except Order.DoesNotExist:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
            
            is_client = (order.client == request.user)
            is_provider = (hasattr(request.user, 'provider_profile') and order.provider_profile == request.user.provider_profile)
            
            if not (is_client or is_provider):
                return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
            
            order.status = Order.Status.DISPUTED
            order.save()
            return Response({'status': 'disputed'})

    @action(detail=True, methods=['get', 'post'], url_path="review")
    def review(self, request, pk=None):
        from .serializers import ReviewSerializer, ReviewCreateSerializer
        
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        # GET: return existing review
        if request.method == 'GET':
            if not hasattr(order, 'review'):
                return Response({"detail": "No review for this order yet."}, status=status.HTTP_404_NOT_FOUND)
            
            # Access control: only participants can view order specific review endpoint
            is_client = (order.client == request.user)
            is_provider = (hasattr(request.user, 'provider_profile') and order.provider_profile == request.user.provider_profile)
            if not (is_client or is_provider):
                return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
                
            serializer = ReviewSerializer(order.review)
            return Response(serializer.data)
            
        # POST: create new review
        elif request.method == 'POST':
            if order.client != request.user:
                return Response({"detail": "Only the client can review this order."}, status=status.HTTP_403_FORBIDDEN)
                
            if order.status != Order.Status.COMPLETED:
                return Response({"detail": "Order must be COMPLETED to leave a review."}, status=status.HTTP_400_BAD_REQUEST)
                
            if hasattr(order, 'review'):
                return Response({"detail": "Order has already been reviewed."}, status=status.HTTP_400_BAD_REQUEST)
                
            serializer = ReviewCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            review = Review.objects.create(
                order=order,
                client=request.user,
                provider_profile=order.provider_profile,
                rating=serializer.validated_data['rating'],
                text=serializer.validated_data.get('text', '')
            )
            
            # Trigger: NEW_REVIEW (notify provider)
            safe_create_notification(
                user=order.provider_profile.user,
                title="Новый отзыв",
                message=f"Клиент оставил отзыв об услуге по заказу #{order.id}.",
                n_type=NotificationModel.NotificationType.NEW_REVIEW,
                metadata={
                    'order_id': order.id,
                    'review_id': review.id
                }
            )
            
            return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post', 'patch'], url_path="review/reply")
    def review_reply(self, request, pk=None):
        from .serializers import ReviewReplySerializer, ReviewSerializer
        
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
            
        if not hasattr(order, 'review'):
            return Response({"detail": "No review exists for this order yet."}, status=status.HTTP_400_BAD_REQUEST)
            
        if not hasattr(request.user, 'provider_profile') or order.provider_profile != request.user.provider_profile:
            return Response({"detail": "Only the provider of this order can reply to the review."}, status=status.HTTP_403_FORBIDDEN)
            
        serializer = ReviewReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        review = order.review
        if review.provider_reply:
            return Response({"detail": "Reply has already been submitted for this review."}, status=status.HTTP_400_BAD_REQUEST)
        review.provider_reply = serializer.validated_data['provider_reply']
        review.save(update_fields=['provider_reply', 'updated_at'])
        
        # Trigger: PROVIDER_REPLY (notify client)
        safe_create_notification(
            user=order.client,
            title="Ответ на отзыв",
            message=f"Исполнитель ответил на ваш отзыв по заказу #{order.id}.",
            n_type=NotificationModel.NotificationType.PROVIDER_REPLY,
            metadata={
                'order_id': order.id,
                'review_id': review.id
            }
        )
        
        return Response(ReviewSerializer(review).data)


class ReviewViewSet(mixins.CreateModelMixin,
                    mixins.ListModelMixin,
                    viewsets.GenericViewSet):
    """
    API для Отзывов.
    """
    queryset = Review.objects.all().select_related('order', 'client', 'provider_profile').prefetch_related('media')
    serializer_class = ReviewSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        order = serializer.validated_data['order']
        # Double check permission
        if order.client != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You can only review your own orders.")
            
        review = serializer.save(
            client=self.request.user,
            provider_profile=order.provider_profile
        )

        # Trigger: NEW_REVIEW (notify provider)
        safe_create_notification(
            user=order.provider_profile.user,
            title="Новый отзыв",
            message=f"Клиент оставил отзыв об услуге по заказу #{order.id}.",
            n_type=NotificationModel.NotificationType.NEW_REVIEW,
            metadata={
                'order_id': order.id,
                'review_id': review.id
            }
        )

    def get_queryset(self):
        qs = super().get_queryset()
        provider_id = self.request.query_params.get('provider_id')
        if not provider_id:
            # Check if used in nested router or custom path
            provider_id = self.kwargs.get('provider_id')
            
        if provider_id:
            qs = qs.filter(provider_profile_id=provider_id)
        return qs
