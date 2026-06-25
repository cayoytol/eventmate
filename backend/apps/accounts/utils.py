import random
import secrets
import string
import uuid
import logging
from django.core.cache import cache
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

# Constants
OTP_TTL = 300  # 5 minutes
EMAIL_TOKEN_TTL = 86400  # 24 hours
MAX_OTP_ATTEMPTS = 5

def generate_email_token(user):
    """
    Generate a unique token for email verification.
    """
    token = str(uuid.uuid4())
    key = f"email_verify:{token}"
    cache.set(key, user.id, timeout=EMAIL_TOKEN_TTL)
    return token

def verify_email_token(token):
    key = f"email_verify:{token}"
    user_id = cache.get(key)
    if user_id:
        cache.delete(key)
        return user_id
    return None

def send_mock_email(user, token):
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    link = f"{frontend_url}/verify-email?token={token}"
    subject = 'Verify your EventMate account'
    message = f"Hello {getattr(user, 'username', 'User')}, please verify your email: {link}"
    
    if settings.DEBUG:
        logger.info(f"EMAIL MOCK to {user.email}: {message}")
        print(f"EMAIL MOCK: {link}")
    
    if not settings.DEBUG:
        try:
            send_mail(
                subject,
                message,
                settings.EMAIL_HOST_USER,
                [user.email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Failed to send email: {e}")

def generate_phone_otp(phone):
    """
    Generate 6-digit OTP. 
    Reset attempts counter on new generation.
    """
    code = ''.join(secrets.choice(string.digits) for _ in range(6))
    key = f"phone_otp:{phone}"
    attempts_key = f"phone_otp_attempts:{phone}"
    
    cache.set(key, code, timeout=OTP_TTL)
    cache.delete(attempts_key) # Reset attempts
    return code

def verify_mock_otp(phone, code):
    """
    Verify OTP with rate limiting (brute force protection).
    """
    key = f"phone_otp:{phone}"
    attempts_key = f"phone_otp_attempts:{phone}"
    
    # Check attempts
    try:
        attempts = cache.get(attempts_key) or 0
    except Exception:
        attempts = 0 # Fallback
        
    if attempts >= MAX_OTP_ATTEMPTS:
        logger.warning(f"OTP Rate limit exceeded for {phone}")
        return False
    
    stored_code = cache.get(key)
    
    if not stored_code:
        return False
        
    if str(stored_code) == str(code):
        cache.delete(key)
        cache.delete(attempts_key)
        return True
    
    # Increment attempts
    try:
        cache.incr(attempts_key)
    except ValueError:
        cache.set(attempts_key, 1, timeout=OTP_TTL)
        
    return False

def send_mock_otp_sms(phone, code):
    message = f"EventMate code: {code}"
    if settings.DEBUG:
        logger.info(f"SMS MOCK to {phone}: {message}")
        print(f"SMS MOCK to {phone}: {message}")
    else:
        # TODO: Integrate Twilio/Vonage
        pass
