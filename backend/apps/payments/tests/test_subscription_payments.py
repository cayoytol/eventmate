from decimal import Decimal
import threading
import time
from django.db import transaction, connection, close_old_connections
from django.utils import timezone
from django.conf import settings
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User, ProviderProfile
from apps.billing.models import Plan, Subscription, PromoCode
from apps.payments.models import Payment
from apps.billing.services.checkout import calculate_subscription_price, create_subscription_checkout, generate_request_fingerprint
from apps.billing.services.entitlements import is_subscription_active, get_effective_subscription


class SubscriptionPaymentsTestCase(TransactionTestCase):
    """Unit tests for subscription checkout, snapshots, and idempotency"""

    def setUp(self):
        super().setUp()
        # Create test users and provider profiles
        self.user = User.objects.create_user(
            email="provider@example.com",
            password="testpassword",
            role="provider"
        )
        self.provider_profile = ProviderProfile.objects.create(
            user=self.user,
            bio="Test provider"
        )
        
        # Create standard plans
        self.premium_plan = Plan.objects.create(
            code="premium_monthly",
            name_ru="Премиум Месяц",
            name_en="Premium Month",
            name_kz="Премиум Айы",
            price=Decimal("9900.50"),
            currency="KZT",
            duration_days=30,
            is_active=True,
            limits_json={"max_services": 10}
        )
        
        # Create promo code
        self.promo = PromoCode.objects.create(
            code="DISCOUNT10",
            discount_type="percentage",
            discount_amount=Decimal("10.00"),
            max_uses=100,
            is_active=True
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_decimal_prices_and_snapshots(self):
        """Verify price calculations and snapshots are saved as Decimal and are immutable"""
        # Calculate price check
        prices = calculate_subscription_price(self.premium_plan, self.promo)
        # 9900.50 * 0.10 = 990.05
        self.assertEqual(prices['original_amount'], Decimal("9900.50"))
        self.assertEqual(prices['discount_amount'], Decimal("990.05"))
        self.assertEqual(prices['final_amount'], Decimal("8910.45"))
        
        # Create checkout
        payment, sub, is_reused = create_subscription_checkout(
            provider_profile=self.provider_profile,
            plan=self.premium_plan,
            promo_code_str="DISCOUNT10",
            idempotency_key="test-key-1",
            locale="ru"
        )
        
        self.assertFalse(is_reused)
        self.assertEqual(payment.amount, Decimal("8910.45"))
        self.assertEqual(payment.original_amount, Decimal("9900.50"))
        self.assertEqual(payment.discount_amount, Decimal("990.05"))
        self.assertEqual(payment.plan_code_snapshot, "premium_monthly")
        self.assertEqual(payment.plan_name_ru_snapshot, "Премиум Месяц")
        self.assertEqual(payment.plan_name_en_snapshot, "Premium Month")
        self.assertEqual(payment.plan_name_kz_snapshot, "Премиум Айы")
        self.assertEqual(payment.promo_code_snapshot, "DISCOUNT10")
        
        # Change plan price and name on DB
        self.premium_plan.price = Decimal("15000.00")
        self.premium_plan.name_ru = "Новый Премиум"
        self.premium_plan.save()
        
        # Check that snapshots remain unchanged on payment
        payment.refresh_from_db()
        self.assertEqual(payment.amount, Decimal("8910.45"))
        self.assertEqual(payment.plan_name_ru_snapshot, "Премиум Месяц")

    def test_nullable_dates_and_entitlements(self):
        """Verify that pending subscriptions have null dates and do not grant entitlements"""
        payment, sub, is_reused = create_subscription_checkout(
            provider_profile=self.provider_profile,
            plan=self.premium_plan,
            idempotency_key="test-key-2"
        )
        
        self.assertEqual(sub.status, "pending")
        self.assertIsNone(sub.start_date)
        self.assertIsNone(sub.end_date)
        
        # Verify active checks
        self.assertFalse(is_subscription_active(sub))
        
        # Verify provider has no active entitlements from this subscription
        effective = get_effective_subscription(self.provider_profile)
        self.assertIsNone(effective)  # Free fallback is used, premium not granted

    def test_idempotency_and_fingerprint(self):
        """Verify idempotency key semantics and conflict errors"""
        # First request
        payment1, sub1, is_reused1 = create_subscription_checkout(
            provider_profile=self.provider_profile,
            plan=self.premium_plan,
            promo_code_str="DISCOUNT10",
            idempotency_key="idem-key"
        )
        
        # Identical replay returns same payment
        payment2, sub2, is_reused2 = create_subscription_checkout(
            provider_profile=self.provider_profile,
            plan=self.premium_plan,
            promo_code_str="DISCOUNT10",
            idempotency_key="idem-key"
        )
        self.assertEqual(payment1.id, payment2.id)
        
        # Replay with different plan raises conflict
        other_plan = Plan.objects.create(
            code="other_plan",
            price=Decimal("5000.00"),
            currency="KZT",
            duration_days=30,
            is_active=True
        )
        from apps.billing.exceptions import IdempotencyConflictError
        with self.assertRaises(IdempotencyConflictError):
            create_subscription_checkout(
                provider_profile=self.provider_profile,
                plan=other_plan,
                idempotency_key="idem-key"
            )

    def test_process_recovery_and_timeouts(self):
        """Verify stale initializing checkouts can be reclaimed, but fresh ones cannot"""
        payment, sub, is_reused = create_subscription_checkout(
            provider_profile=self.provider_profile,
            plan=self.premium_plan,
            idempotency_key="timeout-key"
        )
        
        # Set to initializing manually for testing
        payment.checkout_state = Payment.CheckoutState.INITIALIZING
        payment.checkout_initialization_started_at = timezone.now()
        payment.save()
        
        # Fresh initializing checkout within timeout - should not reclaim
        payment2, sub2, is_reused2 = create_subscription_checkout(
            provider_profile=self.provider_profile,
            plan=self.premium_plan,
            idempotency_key="timeout-key"
        )
        self.assertEqual(payment2.checkout_state, Payment.CheckoutState.INITIALIZING)
        
        # Stale initializing checkout - should reclaim
        payment.checkout_initialization_started_at = timezone.now() - timezone.timedelta(seconds=120)
        payment.save()
        
        payment3, sub3, is_reused3 = create_subscription_checkout(
            provider_profile=self.provider_profile,
            plan=self.premium_plan,
            idempotency_key="timeout-key"
        )
        # After reclaim it goes to ready (mock adapter completes successfully)
        self.assertEqual(payment3.checkout_state, Payment.CheckoutState.READY)
        self.assertEqual(payment3.id, payment.id)

    def test_zero_amount_policy(self):
        """Verify zero-amount checks create pending checkout without payment provider errors"""
        zero_plan = Plan.objects.create(
            code="promo_free_plan",
            price=Decimal("0.00"),
            currency="KZT",
            duration_days=30,
            is_active=True
        )
        payment, sub, is_reused = create_subscription_checkout(
            provider_profile=self.provider_profile,
            plan=zero_plan,
            idempotency_key="zero-key"
        )
        self.assertEqual(payment.amount, Decimal("0.00"))
        self.assertEqual(payment.checkout_state, Payment.CheckoutState.READY)
        self.assertIsNotNone(payment.checkout_url)


import django.db
import os

class SubscriptionPaymentsConcurrencyTestCase(TransactionTestCase):
    """PostgreSQL concurrency smoke test mimicking parallel checkout requests.
    
    Uses service-layer calls directly (not HTTP client) so that threads can
    access the test database via their own connections.  Under SQLite the tests
    are skipped because SQLite serialises all writes and cannot demonstrate
    real row-level lock contention.
    """

    def setUp(self):
        super().setUp()
        # Skip under SQLite – concurrency behaviour cannot be verified there.
        if django.db.connection.vendor == "sqlite":
            self.skipTest("Concurrency tests require PostgreSQL; skipping under SQLite.")
        
        self.user = User.objects.create_user(
            email="concurrent@example.com",
            password="testpassword",
            role="provider"
        )
        self.provider_profile = ProviderProfile.objects.create(
            user=self.user,
            bio="Concurrent test provider"
        )
        self.plan = Plan.objects.create(
            code="concurrency_premium",
            name_ru="Премиум",
            name_en="Concurrency Premium",
            name_kz="Конкуренттік премиум",
            price=Decimal("9900.00"),
            currency="KZT",
            duration_days=30,
            is_active=True,
            limits_json={"max_services": 10}
        )

    def test_concurrent_idempotency_claims(self):
        """Simultaneous requests with same Idempotency-Key create exactly one Payment"""
        barrier = threading.Barrier(2)
        results = []

        def worker(idem_key):
            connection.close()
            barrier.wait()
            try:
                payment, _sub, _reused = create_subscription_checkout(
                    provider_profile=self.provider_profile,
                    plan_code="concurrency_premium",
                    idempotency_key=idem_key,
                )
                results.append(("ok", payment.id))
            except Exception as e:
                results.append(("err", str(e)))
            finally:
                connection.close()

        t1 = threading.Thread(target=worker, args=("key-concurrent-a",))
        t2 = threading.Thread(target=worker, args=("key-concurrent-a",))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        # Both workers should succeed; idempotency means same Payment returned
        self.assertEqual(len(results), 2)
        ok_results = [r for r in results if r[0] == "ok"]
        self.assertGreaterEqual(len(ok_results), 1, f"Expected at least one success; got: {results}")

        payments = Payment.objects.filter(provider_profile=self.provider_profile)
        self.assertEqual(payments.count(), 1, "Idempotency must produce exactly one Payment")
        self.assertEqual(
            Subscription.objects.filter(provider_profile=self.provider_profile).count(),
            1,
            "Idempotency must produce exactly one Subscription"
        )

    def test_concurrent_idempotency_conflict(self):
        """Simultaneous requests with same key but different plan returns conflict"""
        other_plan = Plan.objects.create(
            code="concurrency_other",
            name_ru="Другой",
            name_en="Other Plan",
            name_kz="Басқа жоспар",
            price=Decimal("15000.00"),
            currency="KZT",
            duration_days=60,
            is_active=True,
            limits_json={"max_services": 20}
        )

        barrier = threading.Barrier(2)
        results = []

        def worker(idem_key, plan_code):
            connection.close()
            barrier.wait()
            try:
                payment, _sub, _reused = create_subscription_checkout(
                    provider_profile=self.provider_profile,
                    plan_code=plan_code,
                    idempotency_key=idem_key,
                )
                results.append(("ok", payment.id))
            except Exception as e:
                results.append(("err", str(e)))
            finally:
                connection.close()

        t1 = threading.Thread(target=worker, args=("key-concurrent-c", "concurrency_premium"))
        t2 = threading.Thread(target=worker, args=("key-concurrent-c", "concurrency_other"))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        self.assertEqual(len(results), 2)
        # At least one conflict error must be raised
        err_results = [r for r in results if r[0] == "err"]
        self.assertGreaterEqual(len(err_results), 1, f"Expected at least one idempotency conflict; got: {results}")
        # Only one Payment must exist
        self.assertEqual(
            Payment.objects.filter(provider_profile=self.provider_profile).count(),
            1,
            "Idempotency conflict must produce only one Payment"
        )

    def test_concurrent_no_key_compatible_reuse(self):
        """Deterministic overlap test for compatible no-key checkouts (Stage 31.2G).
        Worker 1 enters adapter and blocks; Worker 2 makes request and reuses first.
        """
        from unittest.mock import patch
        from apps.billing.services.payment_adapters import MockSubscriptionPaymentAdapter
        
        MockSubscriptionPaymentAdapter.reset_call_count()
        
        # Primitives
        adapter_entered = threading.Event()
        adapter_release = threading.Event()
        
        class DeterministicBlockingPaymentAdapter(MockSubscriptionPaymentAdapter):
            def __init__(self, entered_evt, release_evt):
                super().__init__()
                self.entered_evt = entered_evt
                self.release_evt = release_evt
                self.local_call_count = 0
                self.lock = threading.Lock()
                
            def create_checkout(self, payment, locale=None):
                with self.lock:
                    self.local_call_count += 1
                with self._lock:
                    self.__class__._call_count += 1
                    
                self.entered_evt.set()
                # Use finite timeout to prevent infinite test hangs
                released = self.release_evt.wait(timeout=10.0)
                if not released:
                    raise RuntimeError("Test adapter release event timed out")
                return super().create_checkout(payment, locale)
                
        test_adapter = DeterministicBlockingPaymentAdapter(adapter_entered, adapter_release)
        
        results = []
        
        def worker1():
            connection.close()
            client = APIClient()
            client.force_authenticate(user=self.user)
            try:
                # Patch get_subscription_payment_adapter to return test_adapter
                with patch('apps.billing.services.checkout.get_subscription_payment_adapter', return_value=test_adapter):
                    response = client.post(
                        '/api/v1/billing/subscription/checkout/',
                        {"plan_code": "concurrency_premium"}
                    )
                    results.append(("w1", response.status_code, response.data))
            except Exception as e:
                results.append(("w1_err", str(e)))
            finally:
                connection.close()
                
        def worker2():
            connection.close()
            client = APIClient()
            client.force_authenticate(user=self.user)
            try:
                with patch('apps.billing.services.checkout.get_subscription_payment_adapter', return_value=test_adapter):
                    response = client.post(
                        '/api/v1/billing/subscription/checkout/',
                        {"plan_code": "concurrency_premium"}
                    )
                    results.append(("w2", response.status_code, response.data))
            except Exception as e:
                results.append(("w2_err", str(e)))
            finally:
                connection.close()

        # 1. Start worker 1
        t1 = threading.Thread(target=worker1)
        t1.start()
        
        # 2. Wait for worker 1 to enter the adapter
        entered = adapter_entered.wait(timeout=10.0)
        self.assertTrue(entered, "Worker 1 did not enter adapter within timeout")
        
        # 3. Start worker 2 while worker 1 remains blocked in adapter
        t2 = threading.Thread(target=worker2)
        t2.start()
        
        # Join worker 2 first (it should finish immediately because it reuses the initializing payment and doesn't call adapter)
        t2.join(timeout=15.0)
        
        # 4. Release worker 1
        adapter_release.set()
        
        # Join worker 1
        t1.join(timeout=15.0)
        
        # Assertions
        w1_res = [r for r in results if r[0] == "w1"]
        w2_res = [r for r in results if r[0] == "w2"]
        
        self.assertEqual(len(w1_res), 1)
        self.assertEqual(len(w2_res), 1)
        
        w1_status, w1_data = w1_res[0][1], w1_res[0][2]
        w2_status, w2_data = w2_res[0][1], w2_res[0][2]
        
        # Worker 1 succeeds with 201 Created (since it completed and ready checkout is returned)
        self.assertEqual(w1_status, status.HTTP_201_CREATED)
        # Worker 2 returns 202 Accepted because the payment was initializing when it hit Phase A
        self.assertEqual(w2_status, status.HTTP_202_ACCEPTED)
        self.assertEqual(w2_data.get('code'), 'checkout_initializing')
        
        # Assertions from Correction 7
        payments = Payment.objects.filter(provider_profile=self.provider_profile, plan_code_snapshot="concurrency_premium")
        self.assertEqual(payments.count(), 1, "Exactly one subscription Payment must exist")
        payment = payments.first()
        
        subs = Subscription.objects.filter(provider_profile=self.provider_profile, plan__code="concurrency_premium")
        self.assertEqual(subs.count(), 1, "Exactly one pending Subscription must exist")
        sub = subs.first()
        self.assertEqual(sub.status, 'pending')
        
        self.assertEqual(test_adapter.local_call_count, 1, "Adapter invocation count must equal 1")
        self.assertEqual(w1_data.get('id'), w2_data.get('payment_id'), "Both responses must reference the same Payment ID")
        self.assertNotIn('checkout_url', w2_data, "Second response must not contain a newly generated checkout URL")
        
        # Final states check after Phase C completion
        payment.refresh_from_db()
        self.assertEqual(payment.checkout_state, Payment.CheckoutState.READY, "Final checkout_state must be ready")
        self.assertEqual(payment.status, Payment.Status.PENDING, "Final Payment status must be pending")
        self.assertTrue(bool(payment.checkout_url), "Final checkout_url must be populated")
        self.assertIsNotNone(payment.checkout_expires_at, "checkout_expires_at must be populated")
        
        self.assertIsNone(sub.start_date, "pending Subscription start_date must be None")
        self.assertIsNone(sub.end_date, "pending Subscription end_date must be None")
        self.assertFalse(is_subscription_active(sub), "effective paid entitlements must remain inactive")

    def test_concurrent_idempotency_promo_conflict(self):
        """Same Idempotency-Key and different promo code.
        Expected: HTTP 409 conflict, no second Payment, no second adapter call.
        """
        from apps.billing.services.payment_adapters import MockSubscriptionPaymentAdapter
        MockSubscriptionPaymentAdapter.reset_call_count()
        
        # Create promo codes
        promo1 = PromoCode.objects.create(
            code="PCONC1",
            discount_type="percentage",
            discount_amount=Decimal("10.00"),
            is_active=True,
            max_uses=100
        )
        promo2 = PromoCode.objects.create(
            code="PCONC2",
            discount_type="percentage",
            discount_amount=Decimal("15.00"),
            is_active=True,
            max_uses=100
        )

        barrier = threading.Barrier(2)
        results = []

        def worker(promo_str):
            connection.close()
            barrier.wait()
            try:
                payment, _sub, _reused = create_subscription_checkout(
                    provider_profile=self.provider_profile,
                    plan_code="concurrency_premium",
                    promo_code_str=promo_str,
                    idempotency_key="promo-idem-key",
                )
                results.append(("ok", payment.id))
            except Exception as e:
                results.append(("err", str(e)))
            finally:
                connection.close()

        t1 = threading.Thread(target=worker, args=("PCONC1",))
        t2 = threading.Thread(target=worker, args=("PCONC2",))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        self.assertEqual(len(results), 2)
        ok_results = [r for r in results if r[0] == "ok"]
        err_results = [r for r in results if r[0] == "err"]
        
        # Exactly one should succeed and one should raise an IdempotencyConflictError
        self.assertEqual(len(ok_results), 1)
        self.assertEqual(len(err_results), 1)
        self.assertIn("idempotency_conflict", err_results[0][1].lower())
        
        # Check database records
        self.assertEqual(
            Payment.objects.filter(provider_profile=self.provider_profile).count(),
            1,
            "Should only create exactly one Payment"
        )
        # Check that adapter was called exactly once (the conflict should NOT invoke the adapter)
        self.assertEqual(MockSubscriptionPaymentAdapter.get_call_count(), 1)

    def test_fresh_initialization_protection(self):
        """Fresh initializing checkout cannot be claimed or stolen within timeout (Correction 8)"""
        from apps.billing.services.payment_adapters import MockSubscriptionPaymentAdapter
        MockSubscriptionPaymentAdapter.reset_call_count()
        
        # Create subscription
        sub = Subscription.objects.create(
            provider_profile=self.provider_profile,
            plan=self.plan,
            status="pending"
        )
        # Create a fresh initializing payment
        start_time = timezone.now()
        payment = Payment.objects.create(
            provider_profile=self.provider_profile,
            subscription=sub,
            amount=self.plan.price,
            currency=self.plan.currency,
            status=Payment.Status.PENDING,
            checkout_state=Payment.CheckoutState.INITIALIZING,
            checkout_initialization_started_at=start_time,
            plan_code_snapshot=self.plan.code,
            provider="mock"
        )
        
        # Submit duplicate request
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.post(
            '/api/v1/billing/subscription/checkout/',
            {"plan_code": "concurrency_premium"}
        )
        
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data.get('code'), 'checkout_initializing')
        self.assertEqual(response.data.get('payment_id'), payment.id)
        
        # Verify no new Payment/Subscription
        self.assertEqual(Payment.objects.filter(provider_profile=self.provider_profile).count(), 1)
        self.assertEqual(Subscription.objects.filter(provider_profile=self.provider_profile).count(), 1)
        self.assertEqual(MockSubscriptionPaymentAdapter.get_call_count(), 0)
        
        # Verify initialization owner/started_at is not modified
        payment.refresh_from_db()
        self.assertEqual(payment.checkout_initialization_started_at, start_time)

    def test_concurrent_stale_reclaim_race(self):
        """Stale initialization reclaim race (Correction 9).
        Two concurrent requests attempt to reclaim a stale initializing payment.
        Exactly one succeeds in reclaiming and calls the adapter; the other is blocked and reuses it.
        """
        from unittest.mock import patch
        from apps.billing.services.payment_adapters import MockSubscriptionPaymentAdapter
        
        # Create a stale initializing payment manually
        init_timeout = getattr(settings, 'BILLING_CHECKOUT_INITIALIZATION_TIMEOUT_SECONDS', 60)
        stale_time = timezone.now() - timezone.timedelta(seconds=init_timeout + 10)
        
        sub = Subscription.objects.create(
            provider_profile=self.provider_profile,
            plan=self.plan,
            status="pending"
        )
        payment = Payment.objects.create(
            provider_profile=self.provider_profile,
            subscription=sub,
            amount=self.plan.price,
            currency=self.plan.currency,
            status=Payment.Status.PENDING,
            checkout_state=Payment.CheckoutState.INITIALIZING,
            checkout_initialization_started_at=stale_time,
            plan_code_snapshot=self.plan.code,
            provider="mock"
        )
        
        MockSubscriptionPaymentAdapter.reset_call_count()
        
        adapter_entered = threading.Event()
        adapter_release = threading.Event()
        
        class ReclaimBlockingAdapter(MockSubscriptionPaymentAdapter):
            def __init__(self, entered_evt, release_evt):
                super().__init__()
                self.entered_evt = entered_evt
                self.release_evt = release_evt
                self.local_call_count = 0
                self.lock = threading.Lock()
                
            def create_checkout(self, payment, locale=None):
                with self.lock:
                    self.local_call_count += 1
                with self._lock:
                    self.__class__._call_count += 1
                self.entered_evt.set()
                released = self.release_evt.wait(timeout=10.0)
                if not released:
                    raise RuntimeError("Reclaim adapter release event timed out")
                return super().create_checkout(payment, locale)
                
        test_adapter = ReclaimBlockingAdapter(adapter_entered, adapter_release)
        
        results = []
        
        def worker1():
            connection.close()
            client = APIClient()
            client.force_authenticate(user=self.user)
            try:
                with patch('apps.billing.services.checkout.get_subscription_payment_adapter', return_value=test_adapter):
                    response = client.post(
                        '/api/v1/billing/subscription/checkout/',
                        {"plan_code": "concurrency_premium"}
                    )
                    results.append(("w1", response.status_code, response.data))
            except Exception as e:
                results.append(("w1_err", str(e)))
            finally:
                connection.close()
                
        def worker2():
            connection.close()
            client = APIClient()
            client.force_authenticate(user=self.user)
            try:
                with patch('apps.billing.services.checkout.get_subscription_payment_adapter', return_value=test_adapter):
                    response = client.post(
                        '/api/v1/billing/subscription/checkout/',
                        {"plan_code": "concurrency_premium"}
                    )
                    results.append(("w2", response.status_code, response.data))
            except Exception as e:
                results.append(("w2_err", str(e)))
            finally:
                connection.close()

        # Start worker 1
        t1 = threading.Thread(target=worker1)
        t1.start()
        
        # Wait for worker 1 to reclaim and enter the adapter
        entered = adapter_entered.wait(timeout=10.0)
        self.assertTrue(entered, "Worker 1 did not enter reclaim adapter within timeout")
        
        # Start worker 2
        t2 = threading.Thread(target=worker2)
        t2.start()
        
        # Join worker 2 (should finish immediately returning 202)
        t2.join(timeout=10.0)
        
        # Release worker 1
        adapter_release.set()
        t1.join(timeout=10.0)
        
        # Check results
        w1_res = [r for r in results if r[0] == "w1"]
        w2_res = [r for r in results if r[0] == "w2"]
        
        self.assertEqual(len(w1_res), 1)
        self.assertEqual(len(w2_res), 1)
        
        # Worker 1 succeeds
        self.assertEqual(w1_res[0][1], status.HTTP_201_CREATED)
        # Worker 2 is losing request, gets reused/initializing 202 state
        self.assertEqual(w2_res[0][1], status.HTTP_202_ACCEPTED)
        self.assertEqual(w2_res[0][2].get('code'), 'checkout_initializing')
        self.assertEqual(w2_res[0][2].get('payment_id'), payment.id)
        
        # Assertions
        # - exactly one subscription Payment exists
        self.assertEqual(Payment.objects.filter(provider_profile=self.provider_profile).count(), 1)
        # - exactly one Subscription exists
        self.assertEqual(Subscription.objects.filter(provider_profile=self.provider_profile).count(), 1)
        # - exactly one adapter call occurs
        self.assertEqual(test_adapter.local_call_count, 1)
        
        # - final checkout_state becomes ready
        payment.refresh_from_db()
        self.assertEqual(payment.checkout_state, Payment.CheckoutState.READY)



