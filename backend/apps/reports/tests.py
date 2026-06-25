from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.utils import timezone
from apps.accounts.models import ProviderProfile
from apps.catalog.models import Category, Service
from apps.comments.models import ServiceComment
from apps.marketplace.models import EventRequest, Offer, Order, Review
from apps.reports.models import Report

User = get_user_model()

class ReportAPITests(APITestCase):
    def setUp(self):
        # Users
        self.client_user = User.objects.create_user(
            email="client@test.com", password="password123", role="client"
        )
        self.provider_user = User.objects.create_user(
            email="provider@test.com", password="password123", role="provider"
        )
        self.other_user = User.objects.create_user(
            email="other@test.com", password="password123", role="client"
        )
        self.staff_user = User.objects.create_user(
            email="staff@test.com", password="password123", is_staff=True, is_superuser=True
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

        # Comment (on service, by other_user)
        self.comment = ServiceComment.objects.create(
            service=self.service,
            user=self.other_user,
            text="Nice service!"
        )

        # Order to create a Review (Review needs a completed/confirmed order)
        # Event Request
        self.event_request = EventRequest.objects.create(
            client=self.other_user,
            category=self.category,
            title="Need service",
            city="Almaty",
            event_date=timezone.now(),
            description="Details"
        )
        # Offer
        self.offer = Offer.objects.create(
            request=self.event_request,
            service=self.service,
            provider_profile=self.provider_profile,
            price=1000,
            status=Offer.Status.ACCEPTED
        )
        # Order
        self.order = Order.objects.create(
            offer=self.offer,
            client=self.other_user,
            provider_profile=self.provider_profile,
            status=Order.Status.COMPLETED,
            price_agreed=1000
        )
        # Review
        self.review = Review.objects.create(
            order=self.order,
            client=self.other_user,
            provider_profile=self.provider_profile,
            rating=5,
            text="Excellent work!"
        )

        # URLs
        self.reports_url = "/api/v1/reports/"
        self.my_reports_url = "/api/v1/reports/my/"

    def test_guest_cannot_report(self):
        # Guest should be blocked
        data = {
            "content_type": "service",
            "object_id": self.service.id,
            "reason": "spam",
            "message": "Spam service"
        }
        response = self.client.post(self.reports_url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_client_reports_service_success(self):
        self.client.force_authenticate(user=self.client_user)
        data = {
            "content_type": "service",
            "object_id": self.service.id,
            "reason": "inappropriate",
            "message": "Inappropriate service"
        }
        response = self.client.post(self.reports_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Report.objects.count(), 1)
        
        report = Report.objects.first()
        self.assertEqual(report.reporter, self.client_user)
        self.assertEqual(report.content_type, "service")
        self.assertEqual(report.object_id, self.service.id)
        self.assertEqual(report.reason, "inappropriate")
        self.assertEqual(report.message, "Inappropriate service")
        self.assertEqual(report.status, "open")

    def test_client_reports_provider_success(self):
        self.client.force_authenticate(user=self.client_user)
        data = {
            "content_type": "provider",
            "object_id": self.provider_profile.id,
            "reason": "fraud",
            "message": "Fraudulent provider"
        }
        response = self.client.post(self.reports_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_client_reports_comment_success(self):
        self.client.force_authenticate(user=self.client_user)
        data = {
            "content_type": "comment",
            "object_id": self.comment.id,
            "reason": "abuse",
            "message": "Abusive comment"
        }
        response = self.client.post(self.reports_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_client_reports_review_success(self):
        self.client.force_authenticate(user=self.client_user)
        data = {
            "content_type": "review",
            "object_id": self.review.id,
            "reason": "other",
            "message": "Other issues"
        }
        response = self.client.post(self.reports_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_duplicate_active_report_blocked(self):
        self.client.force_authenticate(user=self.client_user)
        data = {
            "content_type": "service",
            "object_id": self.service.id,
            "reason": "spam",
            "message": "First spam report"
        }
        response = self.client.post(self.reports_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Send second one
        response2 = self.client.post(self.reports_url, data)
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already have an active report", str(response2.data))

    def test_invalid_object_id_blocked(self):
        self.client.force_authenticate(user=self.client_user)
        data = {
            "content_type": "service",
            "object_id": 99999,
            "reason": "spam",
            "message": "Invalid service ID"
        }
        response = self.client.post(self.reports_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Service not found", str(response.data))

    def test_cannot_report_self_provider(self):
        # A provider cannot report their own provider profile
        self.client.force_authenticate(user=self.provider_user)
        data = {
            "content_type": "provider",
            "object_id": self.provider_profile.id,
            "reason": "spam",
            "message": "Reporting myself"
        }
        response = self.client.post(self.reports_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot report yourself", str(response.data))

    def test_cannot_report_own_service(self):
        # A provider cannot report their own service
        self.client.force_authenticate(user=self.provider_user)
        data = {
            "content_type": "service",
            "object_id": self.service.id,
            "reason": "spam",
            "message": "Reporting my own service"
        }
        response = self.client.post(self.reports_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot report your own service", str(response.data))

    def test_cannot_report_own_comment(self):
        # User cannot report their own comment
        self.client.force_authenticate(user=self.other_user)
        data = {
            "content_type": "comment",
            "object_id": self.comment.id,
            "reason": "spam",
            "message": "Reporting my own comment"
        }
        response = self.client.post(self.reports_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot report your own comment", str(response.data))

    def test_cannot_report_own_review(self):
        # User cannot report their own review
        self.client.force_authenticate(user=self.other_user)
        data = {
            "content_type": "review",
            "object_id": self.review.id,
            "reason": "spam",
            "message": "Reporting my own review"
        }
        response = self.client.post(self.reports_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot report your own review", str(response.data))

    def test_ordinary_user_sees_only_own_reports(self):
        # Set up a report by other_user
        Report.objects.create(
            reporter=self.other_user,
            content_type="service",
            object_id=self.service.id,
            reason="spam",
            message="Report by other"
        )
        
        # Set up a report by client_user
        Report.objects.create(
            reporter=self.client_user,
            content_type="service",
            object_id=self.service.id,
            reason="spam",
            message="Report by client"
        )

        # Try to access reports/ via list (should fail)
        self.client.force_authenticate(user=self.client_user)
        response = self.client.get(self.reports_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Try to access reports/my/
        response_my = self.client.get(self.my_reports_url)
        self.assertEqual(response_my.status_code, status.HTTP_200_OK)
        # Should only get 1 report (belonging to client_user)
        results = response_my.json()
        if isinstance(results, dict) and 'results' in results:
            results = results['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['message'], "Report by client")

    def test_staff_sees_all_reports(self):
        # Set up reports
        Report.objects.create(
            reporter=self.other_user,
            content_type="service",
            object_id=self.service.id,
            reason="spam",
            message="Report by other"
        )
        Report.objects.create(
            reporter=self.client_user,
            content_type="service",
            object_id=self.service.id,
            reason="spam",
            message="Report by client"
        )

        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(self.reports_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()
        if isinstance(results, dict) and 'results' in results:
            results = results['results']
        self.assertEqual(len(results), 2)
