from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from django.db import transaction
from apps.audit.utils import log_action, get_client_ip
from .models import Report
from .serializers import ReportSerializer, ReportResolutionSerializer

class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.all().select_related('reporter', 'resolved_by')
    serializer_class = ReportSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'resolve', 'reject', 'set_in_review', 'status']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(reporter=self.request.user)

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)

    @action(detail=False, methods=['get'])
    def my(self, request):
        return self.list(request)

    @action(detail=True, methods=['post'], url_path='set-in-review')
    def set_in_review(self, request, pk=None):
        with transaction.atomic():
            report = self.get_object()
            old_status = report.status
            if report.status != Report.Status.IN_REVIEW:
                report.status = Report.Status.IN_REVIEW
                report.save(update_fields=['status'])
                log_action(
                    actor=request.user,
                    action='REPORT_STATUS_CHANGED',
                    target_type='report',
                    target_id=report.id,
                    ip_address=get_client_ip(request),
                    details_json={'old_status': old_status, 'new_status': 'in_review'}
                )
        return Response({'status': 'in_review'})

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        with transaction.atomic():
            report = self.get_object()
            old_status = report.status
            serializer = ReportResolutionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            report.status = Report.Status.RESOLVED
            report.resolution_note = serializer.validated_data['resolution_note']
            report.resolved_at = timezone.now()
            report.resolved_by = request.user
            report.save()

            log_action(
                actor=request.user,
                action='REPORT_STATUS_CHANGED',
                target_type='report',
                target_id=report.id,
                ip_address=get_client_ip(request),
                details_json={
                    'old_status': old_status,
                    'new_status': 'resolved',
                    'resolution_note': report.resolution_note
                }
            )
        return Response({'status': 'resolved'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        with transaction.atomic():
            report = self.get_object()
            old_status = report.status
            serializer = ReportResolutionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            report.status = Report.Status.REJECTED
            report.resolution_note = serializer.validated_data['resolution_note']
            report.resolved_at = timezone.now()
            report.resolved_by = request.user
            report.save()

            log_action(
                actor=request.user,
                action='REPORT_STATUS_CHANGED',
                target_type='report',
                target_id=report.id,
                ip_address=get_client_ip(request),
                details_json={
                    'old_status': old_status,
                    'new_status': 'rejected',
                    'resolution_note': report.resolution_note
                }
            )
        return Response({'status': 'rejected'})

    @action(detail=True, methods=['patch'])
    def status(self, request, pk=None):
        new_status = request.data.get('status')
        resolution_note = request.data.get('resolution_note', '')

        # Validate status
        valid_statuses = [Report.Status.IN_REVIEW, Report.Status.RESOLVED, Report.Status.REJECTED]
        if new_status not in valid_statuses:
            return Response(
                {"detail": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            report = self.get_object()
            old_status = report.status
            report.status = new_status
            
            if new_status in [Report.Status.RESOLVED, Report.Status.REJECTED]:
                report.resolution_note = resolution_note
                report.resolved_at = timezone.now()
                report.resolved_by = request.user
            
            report.save()

            log_action(
                actor=request.user,
                action='REPORT_STATUS_CHANGED',
                target_type='report',
                target_id=report.id,
                ip_address=get_client_ip(request),
                details_json={
                    'old_status': old_status,
                    'new_status': new_status,
                    'resolution_note': resolution_note
                }
            )

        return Response({
            'status': new_status,
            'resolution_note': report.resolution_note
        }, status=status.HTTP_200_OK)
