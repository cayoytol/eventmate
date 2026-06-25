from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.utils import timezone
from apps.accounts.models import ProviderProfile
from apps.catalog.models import Category, Service
from apps.marketplace.models import EventRequest, Offer, Order, Review
from apps.reports.models import Report
from apps.audit.models import AuditLog

User = get_user_model()

class ModerationAPITests(APITestCase):
    def setUp(self):
        # Users
        self.client_user = User.objects.create_user(
            email="client_mod@test.com", password="password123", role="client"
        )
        self.provider_user = User.objects.create_user(
            email="provider_mod@test.com", password="password123", role="provider"
        )
        self.staff_user = User.objects.create_user(
            email="staff_mod@test.com", password="password123", is_staff=True, is_superuser=True
        )

        # Provider profile
        self.provider_profile = ProviderProfile.objects.create(
            user=self.provider_user,
            bio="Bio test"
        )

        # Category and Service
        self.category = Category.objects.create(name_ru="Design", slug="design")
        self.service = Service.objects.create(
            title="Design Service",
            category=self.category,
            provider=self.provider_profile,
            description="Service Description",
            price_amount=1000,
            price_type="fixed",
            city="Almaty",
            is_active=True
        )

        # A report to moderate
        self.report = Report.objects.create(
            reporter=self.client_user,
            content_type="service",
            object_id=self.service.id,
            reason="spam",
            message="Initial spam report"
        )

        # URLs
        self.report_status_url = f"/api/v1/reports/{self.report.id}/status/"
        self.report_in_review_url = f"/api/v1/reports/{self.report.id}/set-in-review/"
        self.report_resolve_url = f"/api/v1/reports/{self.report.id}/resolve/"
        self.report_reject_url = f"/api/v1/reports/{self.report.id}/reject/"
        
        self.provider_block_url = f"/api/v1/providers/{self.provider_profile.id}/block/"
        self.provider_unblock_url = f"/api/v1/providers/{self.provider_profile.id}/unblock/"
        self.provider_detail_url = f"/api/v1/providers/{self.provider_profile.id}/"
        self.services_url = "/api/v1/services/"

    def test_ordinary_user_cannot_patch_report_status(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.patch(self.report_status_url, {"status": "in_review"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_patch_report_status(self):
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.patch(self.report_status_url, {"status": "in_review"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "in_review")

        # Verify AuditLog
        log = AuditLog.objects.first()
        self.assertIsNotNone(log)
        self.assertEqual(log.actor, self.staff_user)
        self.assertEqual(log.action, 'REPORT_STATUS_CHANGED')
        self.assertEqual(log.target_type, 'report')
        self.assertEqual(log.target_id, self.report.id)
        self.assertEqual(log.details_json.get('new_status'), 'in_review')

    def test_patch_report_status_invalid_rejected(self):
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.patch(self.report_status_url, {"status": "open"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_legacy_status_actions_log_to_audit(self):
        self.client.force_authenticate(user=self.staff_user)
        
        # Test set-in-review
        response = self.client.post(self.report_in_review_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log1 = AuditLog.objects.order_by('-id').first()
        self.assertEqual(log1.action, 'REPORT_STATUS_CHANGED')
        self.assertEqual(log1.details_json.get('new_status'), 'in_review')

        # Test resolve
        response2 = self.client.post(self.report_resolve_url, {"resolution_note": "Approved"})
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        log2 = AuditLog.objects.order_by('-id').first()
        self.assertEqual(log2.action, 'REPORT_STATUS_CHANGED')
        self.assertEqual(log2.details_json.get('new_status'), 'resolved')

        # Reset report
        self.report.status = "open"
        self.report.save()

        # Test reject
        response3 = self.client.post(self.report_reject_url, {"resolution_note": "Spam"})
        self.assertEqual(response3.status_code, status.HTTP_200_OK)
        log3 = AuditLog.objects.order_by('-id').first()
        self.assertEqual(log3.action, 'REPORT_STATUS_CHANGED')
        self.assertEqual(log3.details_json.get('new_status'), 'rejected')

    def test_ordinary_user_cannot_block_unblock_provider(self):
        self.client.force_authenticate(user=self.client_user)
        
        response_block = self.client.post(self.provider_block_url)
        self.assertEqual(response_block.status_code, status.HTTP_403_FORBIDDEN)
        
        response_unblock = self.client.post(self.provider_unblock_url)
        self.assertEqual(response_unblock.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_block_unblock_provider(self):
        self.client.force_authenticate(user=self.staff_user)
        
        # Block
        response_block = self.client.post(self.provider_block_url)
        self.assertEqual(response_block.status_code, status.HTTP_200_OK)
        self.provider_profile.refresh_from_db()
        self.assertTrue(self.provider_profile.is_blocked)

        log1 = AuditLog.objects.order_by('-id').first()
        self.assertEqual(log1.actor, self.staff_user)
        self.assertEqual(log1.action, 'PROVIDER_BLOCKED')
        self.assertEqual(log1.target_type, 'provider')
        self.assertEqual(log1.target_id, self.provider_profile.id)

        # Unblock
        response_unblock = self.client.post(self.provider_unblock_url)
        self.assertEqual(response_unblock.status_code, status.HTTP_200_OK)
        self.provider_profile.refresh_from_db()
        self.assertFalse(self.provider_profile.is_blocked)

        log2 = AuditLog.objects.order_by('-id').first()
        self.assertEqual(log2.action, 'PROVIDER_UNBLOCKED')
        self.assertEqual(log2.target_type, 'provider')
        self.assertEqual(log2.target_id, self.provider_profile.id)

    def test_blocked_provider_cannot_mutate_services(self):
        # Block provider
        self.provider_profile.is_blocked = True
        self.provider_profile.save()

        self.client.force_authenticate(user=self.provider_user)

        # Create service should be blocked
        data = {
            "title": "New Service By Blocked",
            "category": self.category.id,
            "description": "Block me",
            "price_amount": 500,
            "price_type": "fixed",
            "city": "Almaty"
        }
        response_create = self.client.post(self.services_url, data)
        self.assertEqual(response_create.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("blocked", str(response_create.data))

        # Update service should be blocked
        response_update = self.client.patch(f"{self.services_url}{self.service.id}/", {"title": "Changed"})
        self.assertEqual(response_update.status_code, status.HTTP_403_FORBIDDEN)

        # Delete service should be blocked
        response_delete = self.client.delete(f"{self.services_url}{self.service.id}/")
        self.assertEqual(response_delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_blocked_provider_services_hidden_from_public(self):
        # Block provider
        self.provider_profile.is_blocked = True
        self.provider_profile.save()

        # Ordinary client request
        self.client.force_authenticate(user=self.client_user)
        response_client = self.client.get(self.services_url)
        res_data = response_client.json()
        results = res_data.get('results', res_data) if isinstance(res_data, dict) else res_data
        self.assertEqual(len(results), 0)

        # Guest request
        self.client.logout()
        response_guest = self.client.get(self.services_url)
        res_data = response_guest.json()
        results_guest = res_data.get('results', res_data) if isinstance(res_data, dict) else res_data
        self.assertEqual(len(results_guest), 0)

        # Staff can see it
        self.client.force_authenticate(user=self.staff_user)
        response_staff = self.client.get(self.services_url)
        res_data = response_staff.json()
        results_staff = res_data.get('results', res_data) if isinstance(res_data, dict) else res_data
        self.assertEqual(len(results_staff), 1)

    def test_blocked_provider_public_profile_restricted(self):
        # Block provider
        self.provider_profile.is_blocked = True
        self.provider_profile.save()

        # Client request (should fail with 404)
        self.client.force_authenticate(user=self.client_user)
        response_client = self.client.get(self.provider_detail_url)
        self.assertEqual(response_client.status_code, status.HTTP_404_NOT_FOUND)

        # Staff request (should pass)
        self.client.force_authenticate(user=self.staff_user)
        response_staff = self.client.get(self.provider_detail_url)
        self.assertEqual(response_staff.status_code, status.HTTP_200_OK)

    def test_filters_still_work_when_blocked(self):
        # Block provider
        self.provider_profile.is_blocked = True
        self.provider_profile.save()

        # provider=me filter for owner works
        self.client.force_authenticate(user=self.provider_user)
        response_me = self.client.get(f"{self.services_url}?provider=me")
        self.assertEqual(response_me.status_code, status.HTTP_200_OK)
        res_data = response_me.json()
        results_me = res_data.get('results', res_data) if isinstance(res_data, dict) else res_data
        self.assertEqual(len(results_me), 1)

        # numeric provider filter for staff works
        self.client.force_authenticate(user=self.staff_user)
        response_num = self.client.get(f"{self.services_url}?provider={self.provider_profile.id}")
        self.assertEqual(response_num.status_code, status.HTTP_200_OK)
        res_data = response_num.json()
        results_num = res_data.get('results', res_data) if isinstance(res_data, dict) else res_data
        self.assertEqual(len(results_num), 1)
