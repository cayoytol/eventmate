import urllib.parse
import logging

logger = logging.getLogger(__name__)

# Preferred approval link rels in order
PAYPAL_APPROVAL_RELS = ('approve', 'payer-action')


def extract_paypal_approval_url(links: list) -> str:
    """
    Safely extract the external buyer approval URL from a PayPal Orders API links array.
    Accepts the first valid HTTPS URL whose rel is 'approve' or 'payer-action' (in that order).
    Returns the validated URL string, or raises ValueError if none found.
    """
    candidates = {}
    for link in (links or []):
        rel = (link.get('rel') or '').lower()
        href = (link.get('href') or '').strip()
        if rel in PAYPAL_APPROVAL_RELS and rel not in candidates:
            candidates[rel] = href

    # Pick in preferred order
    for rel in PAYPAL_APPROVAL_RELS:
        if rel in candidates:
            url = candidates[rel]
            try:
                validate_paypal_approval_url(url)
                return url
            except ValueError as e:
                logger.warning(f"PayPal link rel='{rel}' failed URL validation: {e}")

    raise ValueError(
        f"No valid approval URL found in PayPal links. Searched rels: {PAYPAL_APPROVAL_RELS}. "
        f"Available rels: {[l.get('rel') for l in (links or [])]}"
    )


def validate_paypal_approval_url(url: str, mode: str = "sandbox") -> bool:
    """
    Validates a PayPal approval URL strictly against security rules.
    Raises ValueError if validation fails.
    """
    if not url:
        raise ValueError("URL is empty.")

    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as e:
        raise ValueError(f"Malformed URL: {str(e)}")

    # 1. Scheme must be HTTPS
    if parsed.scheme.lower() != 'https':
        raise ValueError(f"Invalid URL scheme: '{parsed.scheme}'. Only HTTPS is allowed.")

    # 2. Reject username/password
    if parsed.username or parsed.password:
        raise ValueError("URL must not contain authentication credentials.")

    # 3. Reject ports (except default 443 which urlparse usually omits/nulls)
    if parsed.port and parsed.port != 443:
        raise ValueError(f"Explicit port '{parsed.port}' is not allowed.")

    # 4. Reject fragments
    if parsed.fragment:
        raise ValueError("URL must not contain fragments.")

    # 5. Normalize hostname to lowercase and validate host
    hostname = (parsed.hostname or '').lower()
    if not hostname:
        raise ValueError("URL is missing a hostname.")

    # 6. Reject localhost and IP addresses
    if hostname in ['localhost', '127.0.0.1', '0.0.0.0'] or hostname.startswith('192.168.') or hostname.startswith('10.'):
        raise ValueError(f"Local and private network hostnames are blocked: '{hostname}'")

    # 7. Reject EventMate/Sfera own domains (prevent SSRF-like open redirect)
    own_domains = getattr_safe('FRONTEND_BASE_URL', '')
    if own_domains:
        import urllib.parse as _up
        _own = _up.urlparse(own_domains).hostname or ''
        if _own and hostname == _own.lower():
            raise ValueError(f"Hostname '{hostname}' is the EventMate return domain. Approval URLs must point to PayPal.")

    # 8. Check against explicit sandbox allowlist (no suffix/prefix bypass)
    allowed_hosts = ['sandbox.paypal.com', 'www.sandbox.paypal.com']
    if hostname not in allowed_hosts:
        raise ValueError(f"Hostname '{hostname}' is not on the PayPal Sandbox allowlist.")

    # 9. Reject javascript, data, relative paths
    if parsed.scheme.lower() in ['javascript', 'data', 'vbscript']:
        raise ValueError("Unsafe URL scheme detected.")

    return True


def getattr_safe(setting_name: str, default='') -> str:
    """Safely get a Django setting without raising ImproperlyConfigured."""
    try:
        from django.conf import settings
        return getattr(settings, setting_name, default) or default
    except Exception:
        return default
