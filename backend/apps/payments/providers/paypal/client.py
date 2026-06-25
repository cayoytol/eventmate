import base64
import json
import urllib.request
import urllib.error
import time
import logging
import threading
from django.conf import settings

logger = logging.getLogger(__name__)

class PayPalClient:
    def __init__(self, client_id: str, client_secret: str, mode: str = "sandbox"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.mode = mode
        self.base_url = getattr(settings, 'PAYPAL_API_BASE_URL', 'https://api-m.sandbox.paypal.com').rstrip('/')
        self._access_token = None
        self._token_expires_at = 0
        self._lock = threading.Lock()

    def _redact(self, message: str) -> str:
        if not message:
            return message
        if self.client_secret and self.client_secret in message:
            message = message.replace(self.client_secret, "[REDACTED_SECRET]")
        if self.client_id and self.client_id in message:
            message = message.replace(self.client_id, "[REDACTED_CLIENT_ID]")
        if self._access_token and self._access_token in message:
            message = message.replace(self._access_token, "[REDACTED_TOKEN]")
        return message

    def get_access_token(self) -> str:
        with self._lock:
            now = time.time()
            # If token is still valid for at least 5 minutes, return it
            if self._access_token and now < self._token_expires_at - 300:
                return self._access_token

            url = f"{self.base_url}/v1/oauth2/token"
            headers = {
                "Accept": "application/json",
                "Accept-Language": "en_US",
            }
            
            auth_str = f"{self.client_id}:{self.client_secret}"
            auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
            headers["Authorization"] = f"Basic {auth_b64}"
            
            data = b"grant_type=client_credentials"
            
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            timeout = getattr(settings, 'PAYMENT_TIMEOUT_SECONDS', 15)
            
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    resp_data = json.loads(response.read().decode('utf-8'))
                    self._access_token = resp_data["access_token"]
                    expires_in = int(resp_data.get("expires_in", 3600))
                    self._token_expires_at = time.time() + expires_in
                    return self._access_token
            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8')
                logger.error(self._redact(f"PayPal OAuth failed with status {e.code}: {err_body}"))
                raise RuntimeError("PayPal OAuth token request failed")
            except Exception as e:
                logger.error(self._redact(f"PayPal OAuth network error: {str(e)}"))
                raise RuntimeError(f"PayPal OAuth failed: {str(e)}")

    def _request(self, path: str, method: str = "GET", payload: dict = None, headers: dict = None, retry_count: int = 1) -> dict:
        url = f"{self.base_url}{path}"
        token = self.get_access_token()
        
        req_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if headers:
            req_headers.update(headers)
            
        data = json.dumps(payload).encode('utf-8') if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        timeout = getattr(settings, 'PAYMENT_TIMEOUT_SECONDS', 15)
        
        for attempt in range(retry_count + 1):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    return json.loads(response.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8')
                if e.code == 401:
                    with self._lock:
                        self._access_token = None
                        self._token_expires_at = 0
                
                # Retry only safe 5xx errors or network glitches, or if it's the last attempt raise
                if attempt == retry_count or e.code < 500:
                    logger.error(self._redact(f"PayPal API error {method} {path} status {e.code}: {err_body}"))
                    try:
                        err_json = json.loads(err_body)
                        message = err_json.get("message") or err_json.get("error_description") or "PayPal API error"
                    except Exception:
                        message = f"PayPal API responded with status {e.code}"
                    raise RuntimeError(message)
                time.sleep(1)
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt == retry_count:
                    logger.error(self._redact(f"PayPal connection error {method} {path}: {str(e)}"))
                    raise RuntimeError(f"PayPal connection failure: {str(e)}")
                time.sleep(1)

    def create_order(self, payload: dict, request_id: str) -> dict:
        headers = {"PayPal-Request-Id": request_id}
        return self._request("/v2/checkout/orders", method="POST", payload=payload, headers=headers)

    def get_order(self, paypal_order_id: str) -> dict:
        return self._request(f"/v2/checkout/orders/{paypal_order_id}", method="GET")

    def capture_order(self, paypal_order_id: str, request_id: str) -> dict:
        headers = {"PayPal-Request-Id": request_id}
        return self._request(f"/v2/checkout/orders/{paypal_order_id}/capture", method="POST", payload={}, headers=headers)

    def verify_webhook(self, headers: dict, webhook_event: dict, webhook_id: str) -> bool:
        def get_header(name):
            meta_name = 'HTTP_' + name.replace('-', '_').upper()
            if meta_name in headers:
                return headers[meta_name]
            for k, v in headers.items():
                if k.lower() == name.lower():
                    return v
            return None

        auth_algo = get_header("paypal-auth-algo")
        cert_url = get_header("paypal-cert-url")
        transmission_id = get_header("paypal-transmission-id")
        transmission_sig = get_header("paypal-transmission-sig")
        transmission_time = get_header("paypal-transmission-time")

        payload = {
            "auth_algo": auth_algo,
            "cert_url": cert_url,
            "transmission_id": transmission_id,
            "transmission_sig": transmission_sig,
            "transmission_time": transmission_time,
            "webhook_id": webhook_id,
            "webhook_event": webhook_event
        }
        
        if not all([auth_algo, cert_url, transmission_id, transmission_sig, transmission_time]):
            logger.error("Missing webhook transmission headers for signature verification")
            return False
            
        try:
            resp = self._request("/v1/notifications/verify-webhook-signature", method="POST", payload=payload)
            return resp.get("verification_status") == "SUCCESS"
        except Exception as e:
            logger.error(f"Webhook signature verification failed: {str(e)}")
            return False


_billing_client = None
_orders_client = None

def get_paypal_billing_client() -> PayPalClient:
    global _billing_client
    client_id = getattr(settings, 'PAYPAL_BILLING_CLIENT_ID', '')
    client_secret = getattr(settings, 'PAYPAL_BILLING_CLIENT_SECRET', '')
    mode = getattr(settings, 'PAYPAL_MODE', 'sandbox')
    
    if _billing_client is None or _billing_client.client_id != client_id or _billing_client.client_secret != client_secret:
        _billing_client = PayPalClient(client_id, client_secret, mode)
    return _billing_client

def get_paypal_orders_client() -> PayPalClient:
    global _orders_client
    client_id = getattr(settings, 'PAYPAL_ORDERS_CLIENT_ID', '')
    client_secret = getattr(settings, 'PAYPAL_ORDERS_CLIENT_SECRET', '')
    mode = getattr(settings, 'PAYPAL_MODE', 'sandbox')
    
    if _orders_client is None or _orders_client.client_id != client_id or _orders_client.client_secret != client_secret:
        _orders_client = PayPalClient(client_id, client_secret, mode)
    return _orders_client
