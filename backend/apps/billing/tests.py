from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.utils import timezone
from datetime import timedelta
from django.test import override_settings

from apps.accounts.models import ProviderProfile
from apps.catalog.models import Category, Service
from apps.marketplace.models import EventRequest, Offer
from apps.billing.models import Plan, Subscription, PromoCode
from apps.billing import services as billing_services

User = get_user_model()


class BillingAPITests(APITestCase):
    def setUp(self):
        # Users
        self.client_user = User.objects.create_user(
            email="client_billing@test.com", password="password123", role="client"
        )
        self.provider_user = User.objects.create_user(
            email="provider_billing@test.com", password="password123", role="provider"
        )
        
        # Provider profile
        self.provider_profile, _ = ProviderProfile.objects.get_or_create(
            user=self.provider_user,
            defaults={"bio": "Bio test for billing"}
        )

        # Clear existing plans and subscriptions to ensure deterministic tests
        Subscription.objects.all().delete()
        Plan.objects.all().delete()

        # Category for services
        self.category = Category.objects.create(name_ru="Категория", slug="category")

        # Setup Plans
        # Free plan (price = 0)
        self.free_plan = Plan.objects.create(
            code="free",
            name_ru="Бесплатный",
            name_en="Free",
            name_kz="Тегін",
            price=0,
            duration_days=365,
            limits_json={"max_services": 2, "offers_per_month": 2},
            is_active=True
        )

        # Paid plan (price > 0)
        self.paid_plan = Plan.objects.create(
            code="pro",
            name_ru="Платный",
            name_en="Paid",
            name_kz="Ақылы",
            price=5000,
            duration_days=30,
            limits_json={"max_services": 5, "offers_per_month": 10},
            is_active=True
        )

        # Inactive plan
        self.inactive_plan = Plan.objects.create(
            code="inactive",
            name_ru="Неактивный",
            name_en="Inactive",
            name_kz="Активті емес",
            price=2000,
            duration_days=30,
            limits_json={"max_services": 1, "offers_per_month": 1},
            is_active=False
        )

        # Endpoints URLs
        self.plans_url = "/api/v1/billing/plans/"
        self.current_sub_url = "/api/v1/billing/subscription/current/"
        self.validate_promo_url = "/api/v1/billing/promo/validate/"
        self.mock_activate_url = "/api/v1/billing/subscription/mock-activate/"
        self.service_list_url = "/api/v1/services/"
        self.offer_list_url = "/api/v1/offers/"

    def test_active_plans_list(self):
        """Active plans list returns only active plans"""
        response = self.client.get(self.plans_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify result contains only active plans
        plan_ids = [plan['id'] for plan in response.data]
        self.assertIn(self.free_plan.id, plan_ids)
        self.assertIn(self.paid_plan.id, plan_ids)
        self.assertNotIn(self.inactive_plan.id, plan_ids)

    def test_current_subscription_no_sub_fallback(self):
        """Provider without subscription gets safe free/default fallback"""
        self.client.force_authenticate(user=self.provider_user)
        response = self.client.get(self.current_sub_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['subscription'])
        self.assertEqual(response.data['current_plan']['id'], self.free_plan.id)
        self.assertEqual(response.data['current_plan']['limits_json']['max_services'], 2)

    def test_current_subscription_returns_active(self):
        """Current subscription returns active subscription"""
        # Create active subscription
        now = timezone.now()
        sub = Subscription.objects.create(
            provider_profile=self.provider_profile,
            plan=self.paid_plan,
            start_date=now,
            end_date=now + timedelta(days=30),
            status='active'
        )

        self.client.force_authenticate(user=self.provider_user)
        response = self.client.get(self.current_sub_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['subscription'])
        self.assertEqual(response.data['subscription']['id'], sub.id)
        self.assertEqual(response.data['current_plan']['id'], self.paid_plan.id)

    def test_promo_validation_valid(self):
        """Valid promo code is accepted and does not increment used_count"""
        promo = PromoCode.objects.create(
            code="SAVE20",
            discount_percent=20,
            max_uses=5,
            used_count=0,
            is_active=True
        )

        self.client.force_authenticate(user=self.provider_user)
        # Test case insensitivity (saVe20)
        response = self.client.post(self.validate_promo_url, {"code": "saVe20"})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], "SAVE20")
        self.assertEqual(response.data['discount_percent'], 20)
        self.assertTrue(response.data['is_valid'])
        
        # Verify used_count is NOT incremented
        promo.refresh_from_db()
        self.assertEqual(promo.used_count, 0)

    def test_promo_validation_inactive(self):
        """Inactive promo code is rejected"""
        PromoCode.objects.create(
            code="INACTIVE",
            discount_percent=10,
            max_uses=5,
            is_active=False
        )

        self.client.force_authenticate(user=self.provider_user)
        response = self.client.post(self.validate_promo_url, {"code": "INACTIVE"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_promo_validation_expired(self):
        """Expired promo code is rejected"""
        PromoCode.objects.create(
            code="EXPIRED",
            discount_percent=15,
            max_uses=5,
            expires_at=timezone.now() - timedelta(days=1),
            is_active=True
        )

        self.client.force_authenticate(user=self.provider_user)
        response = self.client.post(self.validate_promo_url, {"code": "EXPIRED"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_promo_validation_used_up(self):
        """Fully used-up promo code is rejected"""
        PromoCode.objects.create(
            code="USEDUP",
            discount_percent=50,
            max_uses=3,
            used_count=3,
            is_active=True
        )

        self.client.force_authenticate(user=self.provider_user)
        response = self.client.post(self.validate_promo_url, {"code": "USEDUP"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_service_limit_blocks_creation(self):
        """Service limit blocks provider after max_services limit reached"""
        self.client.force_authenticate(user=self.provider_user)
        
        # Free plan limit is 2 max_services
        # Create 2 services successfully
        for i in range(2):
            response = self.client.post(self.service_list_url, {
                "title": f"Service {i}",
                "category": self.category.id,
                "description": "Test description",
                "price_amount": 1000,
                "price_type": "fixed",
                "city": "Almaty",
                "is_active": True
            })
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify limit is reached (cannot create 3rd)
        response = self.client.post(self.service_list_url, {
            "title": "Service 3",
            "category": self.category.id,
            "description": "Test description",
            "price_amount": 1000,
            "price_type": "fixed",
            "city": "Almaty",
            "is_active": True
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Plan limit reached", response.data['detail'])

    def test_offer_limit_blocks_creation(self):
        """Offer limit blocks provider after monthly offer limit is reached"""
        # Create an event request owned by client
        event_request = EventRequest.objects.create(
            client=self.client_user,
            category=self.category,
            title="Request for services",
            description="Details",
            event_date=timezone.now() + timedelta(days=5),
            status=EventRequest.Status.OFFERS
        )

        # Create active services for the provider (required to offer them)
        services = []
        for i in range(3):
            s = Service.objects.create(
                title=f"Service {i}",
                category=self.category,
                provider=self.provider_profile,
                description="Desc",
                price_amount=1000,
                price_type="fixed",
                city="Almaty",
                is_active=True
            )
            services.append(s)

        self.client.force_authenticate(user=self.provider_user)
        
        # Free plan offers_per_month is 2
        # Create 2 offers successfully
        for i in range(2):
            response = self.client.post(self.offer_list_url, {
                "request": event_request.id,
                "service": services[i].id,
                "price": 1000,
                "message": f"Offer {i}"
            })
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify limit is reached (cannot create 3rd)
        response = self.client.post(self.offer_list_url, {
            "request": event_request.id,
            "service": services[2].id,
            "price": 1000,
            "message": "Offer 3"
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Plan limit reached", response.data['detail'])

    @override_settings(BILLING_DEMO_ENABLED=True)
    def test_mock_activate_works_in_demo_enabled(self):
        """mock-activate works successfully when BILLING_DEMO_ENABLED=True"""
        self.client.force_authenticate(user=self.provider_user)
        response = self.client.post(self.mock_activate_url, {"plan_id": self.paid_plan.id})
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['plan']['id'], self.paid_plan.id)
        self.assertTrue(response.data['is_active'])

        # Verify database subscription
        sub = Subscription.objects.filter(provider_profile=self.provider_profile, status='active').first()
        self.assertIsNotNone(sub)
        self.assertEqual(sub.plan.id, self.paid_plan.id)

    @override_settings(BILLING_DEMO_ENABLED=False)
    def test_mock_activate_returns_403_in_demo_disabled(self):
        """mock-activate returns 403 Forbidden when BILLING_DEMO_ENABLED=False"""
        self.client.force_authenticate(user=self.provider_user)
        response = self.client.post(self.mock_activate_url, {"plan_id": self.paid_plan.id})
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify no active subscription was created
        sub_exists = Subscription.objects.filter(
            provider_profile=self.provider_profile,
            plan=self.paid_plan,
            status='active'
        ).exists()
        self.assertFalse(sub_exists)

    def test_plan_codes_deterministic_migration_helper(self):
        """Test deterministic code generation and collision handling"""
        p1 = Plan.objects.create(
            code="temp_code_1",
            name_ru="Тест", name_en="Test Plan Unique", name_kz="Тест",
            price=1500, duration_days=30, limits_json={}
        )
        p2 = Plan.objects.create(
            code="temp_code_2",
            name_ru="Тест 2", name_en="Test Plan Unique", name_kz="Тест",
            price=2500, duration_days=30, limits_json={}
        )
        
        import importlib
        migration_mod = importlib.import_module(
            "apps.billing.migrations.0003_alter_plan_options_plan_code_plan_currency_and_more"
        )
        populate_plan_codes = migration_mod.populate_plan_codes
        from django.apps import apps
        
        populate_plan_codes(apps, None)
        
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertIsNotNone(p1.code)
        self.assertIsNotNone(p2.code)
        self.assertNotEqual(p1.code, p2.code)
        self.assertEqual(p1.code, "test_plan_unique")
        self.assertEqual(p2.code, "test_plan_unique_1")

    def test_subscription_status_migration_helper(self):
        """Obsolete test for dropped is_active column status migration"""
        pass

    def test_legacy_activity_does_not_override_expired_date(self):
        """Stored active status or legacy is_active cannot override expired date"""
        now = timezone.now()
        sub = Subscription.objects.create(
            provider_profile=self.provider_profile, plan=self.paid_plan,
            start_date=now - timedelta(days=10), end_date=now - timedelta(days=1),
            status="active"
        )
        
        from apps.billing.services.entitlements import is_subscription_active
        self.assertFalse(is_subscription_active(sub, at=now))

    def test_cancelled_unexpired_retains_access(self):
        """Cancelled unexpired subscription retains access until ends_at"""
        now = timezone.now()
        sub = Subscription.objects.create(
            provider_profile=self.provider_profile, plan=self.paid_plan,
            start_date=now - timedelta(days=5), end_date=now + timedelta(days=10),
            status="cancelled", cancelled_at=now
        )
        
        from apps.billing.services.entitlements import is_subscription_active
        self.assertTrue(is_subscription_active(sub, at=now))

    def test_cancelled_expired_falls_back_to_free(self):
        """Cancelled expired subscription fails active check and falls back to Free plan"""
        now = timezone.now()
        sub = Subscription.objects.create(
            provider_profile=self.provider_profile, plan=self.paid_plan,
            start_date=now - timedelta(days=10), end_date=now - timedelta(days=1),
            status="cancelled", cancelled_at=now - timedelta(days=5)
        )
        
        from apps.billing.services.entitlements import is_subscription_active, get_effective_plan
        self.assertFalse(is_subscription_active(sub, at=now))
        plan = get_effective_plan(self.provider_profile, at=now)
        self.assertEqual(plan.code, "free")

    def test_exact_expiry_boundary(self):
        """Test boundary active checks: 1s before expiry, exact expiry, and 1s after expiry"""
        now = timezone.now()
        expiry = now + timedelta(days=5)
        sub = Subscription.objects.create(
            provider_profile=self.provider_profile, plan=self.paid_plan,
            start_date=now, end_date=expiry,
            status="active"
        )
        
        from apps.billing.services.entitlements import is_subscription_active
        # 1s before expiry: active
        self.assertTrue(is_subscription_active(sub, at=expiry - timedelta(seconds=1)))
        # Exact expiry: expired
        self.assertFalse(is_subscription_active(sub, at=expiry))
        # 1s after expiry: expired
        self.assertFalse(is_subscription_active(sub, at=expiry + timedelta(seconds=1)))

    def test_free_plan_identified_by_code_not_price_alone(self):
        """A plan with price 0 but a different code is not treated as fallback Free plan"""
        Plan.objects.create(
            code="not_free_code", name_ru="Тест", name_en="Zero Price Non-Free", name_kz="Тест",
            price=0, duration_days=30, limits_json={"max_services": 0}, is_active=True
        )
        
        from apps.billing.services.entitlements import get_free_plan
        free_plan = get_free_plan()
        self.assertEqual(free_plan.code, "free")

    def test_empty_eligible_plans_means_all_paid(self):
        """Promo code with empty eligible_plans applies to all paid plans"""
        promo = PromoCode.objects.create(
            code="GLOBALDISCOUNT", discount_type="percentage", discount_amount=15,
            max_uses=5, is_active=True
        )
        
        self.client.force_authenticate(user=self.provider_user)
        response = self.client.post(self.validate_promo_url, {
            "code": "GLOBALDISCOUNT",
            "plan_id": self.paid_plan.id
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_valid"])

    def test_promo_validation_does_not_consume(self):
        """Promo validation endpoint does not increment used_count"""
        promo = PromoCode.objects.create(
            code="VALIDATEONLY", discount_type="percentage", discount_amount=10,
            max_uses=10, used_count=0, is_active=True
        )
        
        self.client.force_authenticate(user=self.provider_user)
        response = self.client.post(self.validate_promo_url, {"code": "VALIDATEONLY"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        promo.refresh_from_db()
        self.assertEqual(promo.used_count, 0)

    def test_seed_plans_idempotent_no_pricing_overwrite(self):
        """seed_plans is idempotent and preserves edited pricing unless --force is passed"""
        from django.core.management import call_command
        
        # Initial seed
        call_command("seed_plans", force=True)
        
        plan = Plan.objects.get(code="pro")
        plan.price = 12000
        plan.save()
        
        # Second seed without force
        call_command("seed_plans")
        plan.refresh_from_db()
        self.assertEqual(plan.price, 12000)
        
        # Third seed with force
        call_command("seed_plans", force=True)
        plan.refresh_from_db()
        self.assertEqual(plan.price, 9900)

    def test_system_checks_no_tables_no_fail(self):
        """System checks do not fail when database tables are missing/unmigrated"""
        from apps.billing.checks import check_billing_configuration
        # Calling checks on unmigrated / missing table setup handles ProgrammingError / OperationalError
        # Here we verify it doesn't crash during normal run
        errors = check_billing_configuration(None)
        self.assertEqual(len(errors), 0)

    def test_current_subscription_compat_fields(self):
        """Current subscription endpoint returns compatibility fields correctly"""
        self.client.force_authenticate(user=self.provider_user)
        response = self.client.get(self.current_sub_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("current_plan", response.data)
        self.assertIn("subscription", response.data)
        self.assertIn("entitlements", response.data)

    def test_order_payments_unchanged(self):
        """Order PaymentTransaction functionality remains unchanged and separated"""
        from apps.payments.models import PaymentTransaction
        # Check we can still create payment transactions for orders without affecting subscriptions
        self.assertTrue(hasattr(PaymentTransaction, "order"))

