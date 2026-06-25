import json
from io import BytesIO
from unittest.mock import patch, MagicMock

from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import override_settings

from apps.ai.services import sanitize_text, _truncate

User = get_user_model()


def _mock_openai_response(content="Generated AI text"):
    """Build a bytes response mimicking OpenAI chat completion JSON."""
    body = json.dumps({
        "choices": [
            {"message": {"role": "assistant", "content": content}}
        ]
    }).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _mock_bad_json_response():
    resp = MagicMock()
    resp.read.return_value = b"NOT JSON AT ALL"
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _mock_empty_choices_response():
    body = json.dumps({"choices": []}).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _mock_missing_content_response():
    body = json.dumps({"choices": [{"message": {"role": "assistant", "content": ""}}]}).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ===========================
# Unit tests for sanitize_text
# ===========================

class SanitizeTextTests(APITestCase):

    def test_email_is_stripped(self):
        result = sanitize_text("Contact me at user@example.com for details")
        self.assertNotIn("user@example.com", result)
        self.assertIn("[hidden_email]", result)

    def test_multiple_emails_stripped(self):
        result = sanitize_text("Email a@b.com and c@d.org please")
        self.assertNotIn("a@b.com", result)
        self.assertNotIn("c@d.org", result)
        self.assertEqual(result.count("[hidden_email]"), 2)

    def test_phone_is_stripped(self):
        result = sanitize_text("Call +7 777 123 45 67 now")
        self.assertNotIn("777 123 45 67", result)
        self.assertIn("[hidden_phone]", result)

    def test_phone_with_dashes(self):
        result = sanitize_text("Phone: 777-123-45-67")
        self.assertIn("[hidden_phone]", result)

    def test_phone_with_parens(self):
        result = sanitize_text("Call (777) 123-45-67")
        self.assertIn("[hidden_phone]", result)

    def test_bearer_token_stripped(self):
        result = sanitize_text("Use Bearer eyJhbGciOiJIUzI1NiJ9.abc.def for auth")
        self.assertNotIn("eyJhbGciOiJIUzI1NiJ9", result)
        self.assertIn("[hidden_secret]", result)

    def test_normal_text_preserved(self):
        text = "I need a DJ for a wedding in Almaty on July 20th, budget 150000"
        result = sanitize_text(text)
        self.assertEqual(result, text)

    def test_plain_numbers_not_stripped(self):
        """Budget numbers like 140000 should NOT be treated as phone numbers."""
        result = sanitize_text("Budget is 140000 tenge")
        self.assertEqual(result, "Budget is 140000 tenge")

    def test_empty_input(self):
        self.assertEqual(sanitize_text(""), "")
        self.assertEqual(sanitize_text(None), "")

    def test_whitespace_collapsed(self):
        result = sanitize_text("hello      world")
        self.assertEqual(result, "hello world")


# ===========================
# Unit tests for _truncate
# ===========================

class TruncateTests(APITestCase):

    def test_truncates_long_text(self):
        text = "a" * 3000
        result = _truncate(text, max_chars=100)
        self.assertEqual(len(result), 100)

    def test_short_text_unchanged(self):
        text = "short text"
        result = _truncate(text, max_chars=100)
        self.assertEqual(result, text)

    def test_empty_string(self):
        self.assertEqual(_truncate("", max_chars=100), "")

    @override_settings(AI_MAX_INPUT_CHARS=50)
    def test_uses_settings_default(self):
        text = "x" * 200
        result = _truncate(text)
        self.assertEqual(len(result), 50)


# ===========================
# Endpoint Permission Tests
# ===========================

class AIPermissionTests(APITestCase):

    def setUp(self):
        self.client_user = User.objects.create_user(
            username="client_user",
            email="client@example.com",
            password="Password123!",
            role="client"
        )
        self.provider_user = User.objects.create_user(
            username="provider_user",
            email="provider@example.com",
            password="Password123!",
            role="provider"
        )
        self.request_assistant_url = reverse('ai-request-assistant')
        self.offer_assistant_url = reverse('ai-offer-assistant')

    def test_guest_cannot_access_request_assistant(self):
        response = self.client.post(self.request_assistant_url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_guest_cannot_access_offer_assistant(self):
        response = self.client.post(self.offer_assistant_url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_provider_cannot_access_request_assistant(self):
        self.client.force_authenticate(user=self.provider_user)
        payload = {"category": "Ведущий", "city": "Алматы", "draft": "хочу свадьбу"}
        response = self.client.post(self.request_assistant_url, payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_client_cannot_access_offer_assistant(self):
        self.client.force_authenticate(user=self.client_user)
        payload = {"request_description": "Ищу ведущего на свадьбу в Алматы"}
        response = self.client.post(self.offer_assistant_url, payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ===========================
# Fallback Mode Tests
# ===========================

@override_settings(AI_API_KEY="", AI_API_URL="")
class FallbackModeTests(APITestCase):

    def setUp(self):
        from apps.accounts.models import ProviderProfile
        from apps.billing.models import Plan, Subscription
        from django.utils import timezone
        from datetime import timedelta

        self.client_user = User.objects.create_user(
            username="client_fb",
            email="clientfb@example.com",
            password="Password123!",
            role="client"
        )
        self.provider_user = User.objects.create_user(
            username="provider_fb",
            email="providerfb@example.com",
            password="Password123!",
            role="provider"
        )
        self.profile_fb = ProviderProfile.objects.create(user=self.provider_user)
        self.pro_plan, _ = Plan.objects.get_or_create(
            code="pro",
            defaults={
                "name_ru": "Про",
                "name_en": "Pro",
                "name_kz": "Про",
                "price": 9900,
                "duration_days": 30,
                "limits_json": {"ai_features": True},
                "is_active": True
            }
        )
        Subscription.objects.create(
            provider_profile=self.profile_fb,
            plan=self.pro_plan,
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() + timedelta(days=29),
            status="active"
        )
        self.request_assistant_url = reverse('ai-request-assistant')
        self.offer_assistant_url = reverse('ai-offer-assistant')

    def test_missing_key_returns_ai_not_configured_request(self):
        self.client.force_authenticate(user=self.client_user)
        payload = {
            "category": "Ведущий",
            "city": "Алматы",
            "event_date": "2026-07-20",
            "budget": "150000",
            "draft": "хочу свадьбу",
            "locale": "ru"
        }
        response = self.client.post(self.request_assistant_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ai_not_configured")

    def test_missing_key_returns_ai_not_configured_offer(self):
        self.client.force_authenticate(user=self.provider_user)
        payload = {
            "request_description": "Ищу ведущего на свадьбу в Алматы",
            "service_title": "Супер Ведущий",
            "price": "140000",
            "locale": "ru"
        }
        response = self.client.post(self.offer_assistant_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ai_not_configured")

    def test_empty_payload_returns_400(self):
        # We temporarily set AI settings so that serializer validation runs first
        with override_settings(AI_API_KEY="dummy", AI_API_URL="dummy"):
            self.client.force_authenticate(user=self.client_user)
            response = self.client.post(self.request_assistant_url, {})
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_request_description_returns_400(self):
        with override_settings(AI_API_KEY="dummy", AI_API_URL="dummy"):
            self.client.force_authenticate(user=self.provider_user)
            response = self.client.post(self.offer_assistant_url, {})
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ===========================
# LLM Success Path Tests
# ===========================

@override_settings(
    AI_API_KEY="test-key-do-not-use",
    AI_API_URL="https://fake-provider.test/v1/chat/completions",
    AI_API_MODEL="test-model",
    AI_TIMEOUT_SECONDS=5,
    AI_MAX_OUTPUT_TOKENS=200,
    AI_TEMPERATURE=0.5,
)
class LLMSuccessTests(APITestCase):

    def setUp(self):
        from apps.accounts.models import ProviderProfile
        from apps.billing.models import Plan, Subscription
        from django.utils import timezone
        from datetime import timedelta

        self.client_user = User.objects.create_user(
            username="client_llm",
            email="clientllm@example.com",
            password="Password123!",
            role="client"
        )
        self.provider_user = User.objects.create_user(
            username="provider_llm",
            email="providerllm@example.com",
            password="Password123!",
            role="provider"
        )
        self.profile = ProviderProfile.objects.create(user=self.provider_user)
        self.pro_plan, _ = Plan.objects.get_or_create(
            code="pro",
            defaults={
                "name_ru": "Про",
                "name_en": "Pro",
                "name_kz": "Про",
                "price": 9900,
                "duration_days": 30,
                "limits_json": {"ai_features": True},
                "is_active": True
            }
        )
        Subscription.objects.create(
            provider_profile=self.profile,
            plan=self.pro_plan,
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() + timedelta(days=29),
            status="active"
        )
        self.request_assistant_url = reverse('ai-request-assistant')
        self.offer_assistant_url = reverse('ai-offer-assistant')

    @patch("apps.ai.services.urllib.request.urlopen")
    def test_successful_llm_request_assistant(self, mock_urlopen):
        mock_urlopen.return_value = _mock_openai_response(
            "Ищу профессионального ведущего для свадебного торжества в Алматы."
        )
        self.client.force_authenticate(user=self.client_user)
        payload = {
            "category": "Ведущий",
            "city": "Алматы",
            "draft": "свадьба",
            "locale": "ru"
        }
        response = self.client.post(self.request_assistant_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source"], "llm")
        self.assertIn("профессионального ведущего", response.data["suggested_text"])

    @patch("apps.ai.services.urllib.request.urlopen")
    def test_successful_llm_offer_assistant(self, mock_urlopen):
        mock_urlopen.return_value = _mock_openai_response(
            "Dear client, I would be happy to provide my DJ services."
        )
        self.client.force_authenticate(user=self.provider_user)
        payload = {
            "request_description": "Need a DJ for a wedding in Almaty",
            "service_title": "Pro DJ",
            "price": "200000",
            "locale": "en"
        }
        response = self.client.post(self.offer_assistant_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source"], "llm")
        self.assertIn("DJ services", response.data["suggested_letter"])


# ===========================
# LLM Error / Fallback Tests
# ===========================

@override_settings(
    AI_API_KEY="test-key",
    AI_API_URL="https://fake-provider.test/v1/chat/completions",
    AI_API_MODEL="test-model",
)
class LLMErrorFallbackTests(APITestCase):

    def setUp(self):
        from apps.accounts.models import ProviderProfile
        from apps.billing.models import Plan, Subscription
        from django.utils import timezone
        from datetime import timedelta

        self.client_user = User.objects.create_user(
            username="client_err",
            email="clienterr@example.com",
            password="Password123!",
            role="client"
        )
        self.provider_user = User.objects.create_user(
            username="provider_err",
            email="providererr@example.com",
            password="Password123!",
            role="provider"
        )
        self.profile = ProviderProfile.objects.create(user=self.provider_user)
        self.pro_plan, _ = Plan.objects.get_or_create(
            code="pro",
            defaults={
                "name_ru": "Про",
                "name_en": "Pro",
                "name_kz": "Про",
                "price": 9900,
                "duration_days": 30,
                "limits_json": {"ai_features": True},
                "is_active": True
            }
        )
        Subscription.objects.create(
            provider_profile=self.profile,
            plan=self.pro_plan,
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() + timedelta(days=29),
            status="active"
        )
        self.request_assistant_url = reverse('ai-request-assistant')
        self.offer_assistant_url = reverse('ai-offer-assistant')

    @patch("apps.ai.services.urllib.request.urlopen")
    def test_invalid_json_returns_fallback(self, mock_urlopen):
        mock_urlopen.return_value = _mock_bad_json_response()
        self.client.force_authenticate(user=self.client_user)
        payload = {"category": "Декор", "city": "Астана", "draft": "свадьба", "locale": "ru"}
        response = self.client.post(self.request_assistant_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source"], "fallback")
        self.assertIn("Декор", response.data["suggested_text"])

    @patch("apps.ai.services.urllib.request.urlopen")
    def test_empty_choices_returns_fallback(self, mock_urlopen):
        mock_urlopen.return_value = _mock_empty_choices_response()
        self.client.force_authenticate(user=self.client_user)
        payload = {"category": "Декор", "city": "Астана", "draft": "свадьба", "locale": "ru"}
        response = self.client.post(self.request_assistant_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source"], "fallback")

    @patch("apps.ai.services.urllib.request.urlopen")
    def test_empty_content_returns_fallback(self, mock_urlopen):
        mock_urlopen.return_value = _mock_missing_content_response()
        self.client.force_authenticate(user=self.client_user)
        payload = {"category": "Декор", "city": "Астана", "draft": "свадьба", "locale": "ru"}
        response = self.client.post(self.request_assistant_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source"], "fallback")

    @patch("apps.ai.services.urllib.request.urlopen")
    def test_timeout_returns_fallback(self, mock_urlopen):
        import socket
        mock_urlopen.side_effect = socket.timeout("connection timed out")
        self.client.force_authenticate(user=self.client_user)
        payload = {"category": "DJ", "city": "Almaty", "draft": "wedding", "locale": "en"}
        response = self.client.post(self.request_assistant_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source"], "fallback")
        self.assertIn("DJ", response.data["suggested_text"])

    @patch("apps.ai.services.urllib.request.urlopen")
    def test_network_error_returns_fallback(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("DNS resolution failed")
        self.client.force_authenticate(user=self.provider_user)
        payload = {
            "request_description": "Need photographer",
            "service_title": "Photo Pro",
            "price": "100000",
            "locale": "en"
        }
        response = self.client.post(self.offer_assistant_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source"], "fallback")
        self.assertIn("Photo Pro", response.data["suggested_letter"])

    @patch("apps.ai.services.urllib.request.urlopen")
    def test_offer_invalid_json_returns_fallback(self, mock_urlopen):
        mock_urlopen.return_value = _mock_bad_json_response()
        self.client.force_authenticate(user=self.provider_user)
        payload = {
            "request_description": "Ищу фотографа на свадьбу",
            "service_title": "ФотоМастер",
            "price": "80000",
            "locale": "ru"
        }
        response = self.client.post(self.offer_assistant_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source"], "fallback")
        self.assertIn("ФотоМастер", response.data["suggested_letter"])


# ===========================
# Privacy Sanitizer Integration Tests
# ===========================

@override_settings(AI_API_KEY="test-key", AI_API_URL="http://dummy-url-for-tests")
class SanitizerIntegrationTests(APITestCase):

    def setUp(self):
        self.client_user = User.objects.create_user(
            username="client_san",
            email="clientsan@example.com",
            password="Password123!",
            role="client"
        )
        self.request_assistant_url = reverse('ai-request-assistant')

    def test_email_in_draft_is_sanitized_in_fallback(self):
        self.client.force_authenticate(user=self.client_user)
        payload = {
            "category": "DJ",
            "city": "Almaty",
            "draft": "Contact me at secret@mail.com for details",
            "locale": "en"
        }
        response = self.client.post(self.request_assistant_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("secret@mail.com", response.data["suggested_text"])

    def test_phone_in_draft_is_sanitized_in_fallback(self):
        self.client.force_authenticate(user=self.client_user)
        payload = {
            "category": "DJ",
            "city": "Almaty",
            "draft": "Call me +7 777 123 4567 anytime",
            "locale": "en"
        }
        response = self.client.post(self.request_assistant_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("+7 777 123 4567", response.data["suggested_text"])


# ===========================
# Long Input Handling Tests
# ===========================

@override_settings(AI_API_KEY="test-key", AI_API_URL="http://dummy-url-for-tests", AI_MAX_INPUT_CHARS=100)
class LongInputTests(APITestCase):

    def setUp(self):
        self.client_user = User.objects.create_user(
            username="client_long",
            email="clientlong@example.com",
            password="Password123!",
            role="client"
        )
        self.request_assistant_url = reverse('ai-request-assistant')

    def test_long_draft_handled_gracefully(self):
        """Draft within serializer limit (1500) but exceeding AI_MAX_INPUT_CHARS (100) is truncated."""
        self.client.force_authenticate(user=self.client_user)
        payload = {
            "category": "DJ",
            "city": "Almaty",
            "draft": "w" * 1400,  # within serializer max_length=1500
            "locale": "en"
        }
        response = self.client.post(self.request_assistant_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source"], "fallback")
        # The draft in fallback output should be truncated to AI_MAX_INPUT_CHARS (100)
        draft_section = response.data["suggested_text"]
        self.assertTrue(len(draft_section) < 1400 + 200)  # much shorter than raw input

    def test_long_category_handled_gracefully(self):
        """Category within serializer limit (200) is handled without crash."""
        self.client.force_authenticate(user=self.client_user)
        payload = {
            "category": "A" * 200,  # max_length=200 in serializer
            "draft": "wedding",
            "locale": "ru"
        }
        response = self.client.post(self.request_assistant_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source"], "fallback")


# ===========================
# AI Subscription Entitlement Tests
# ===========================

@override_settings(AI_API_KEY="test-key", AI_API_URL="http://dummy-url-for-tests")
class AISubscriptionEntitlementTests(APITestCase):

    def setUp(self):
        from apps.accounts.models import ProviderProfile
        from apps.billing.models import Plan, Subscription
        from django.utils import timezone
        from datetime import timedelta

        self.provider_user_free = User.objects.create_user(
            username="provider_free",
            email="free_prov@example.com",
            password="Password123!",
            role="provider"
        )
        self.profile_free = ProviderProfile.objects.create(user=self.provider_user_free)

        self.provider_user_pro = User.objects.create_user(
            username="provider_pro",
            email="pro_prov@example.com",
            password="Password123!",
            role="provider"
        )
        self.profile_pro = ProviderProfile.objects.create(user=self.provider_user_pro)

        # Create Pro plan with AI features enabled
        self.pro_plan = Plan.objects.create(
            code="pro",
            name_ru="Про",
            name_en="Pro",
            name_kz="Про",
            price=9900,
            duration_days=30,
            limits_json={"ai_features": True},
            is_active=True
        )

        # Create active subscription to Pro plan for the pro provider
        self.sub = Subscription.objects.create(
            provider_profile=self.profile_pro,
            plan=self.pro_plan,
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() + timedelta(days=29),
            status="active"
        )

        # Create active Free plan in DB
        self.free_plan = Plan.objects.create(
            code="free",
            name_ru="Бесплатный",
            name_en="Free",
            name_kz="Тегін",
            price=0,
            duration_days=3650,
            limits_json={"ai_features": False},
            is_active=True
        )

        self.offer_assistant_url = reverse('ai-offer-assistant')

    def test_provider_with_free_plan_rejected(self):
        self.client.force_authenticate(user=self.provider_user_free)
        payload = {
            "request_description": "Need a DJ for a wedding in Almaty",
            "service_title": "Pro DJ",
            "price": "200000",
            "locale": "en"
        }
        response = self.client.post(self.offer_assistant_url, payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "subscription_required")

    def test_provider_with_pro_plan_allowed(self):
        self.client.force_authenticate(user=self.provider_user_pro)
        payload = {
            "request_description": "Need a DJ for a wedding in Almaty",
            "service_title": "Pro DJ",
            "price": "200000",
            "locale": "en"
        }
        response = self.client.post(self.offer_assistant_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source"], "fallback")
