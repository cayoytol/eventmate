import re
import urllib.request
import urllib.error
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Privacy sanitizer — strips PII before sending text to external AI
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
_PHONE_RE = re.compile(
    r'(?:'
    r'\+\d[\d\s\-]{7,15}'           # international: +7 777 123 45 67
    r'|\(\d{2,4}\)[\s\-]?\d[\d\s\-]{5,12}'  # parenthesized area code: (777) 123-45-67
    r'|\b\d{2,4}[\s\-]\d{2,4}[\s\-]\d{2,4}(?:[\s\-]\d{2,4})?\b'  # groups with separators: 777-123-45-67
    r')'
)
_SECRET_RE = re.compile(
    r'(?:Bearer|bearer|BEARER)\s+[A-Za-z0-9\-._~+/]+=*',
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r'[ \t]{3,}')


def sanitize_text(text: str) -> str:
    """Remove emails, phone numbers, bearer tokens, and collapse whitespace."""
    if not text:
        return ""
    result = _EMAIL_RE.sub('[hidden_email]', text)
    result = _SECRET_RE.sub('[hidden_secret]', result)
    result = _PHONE_RE.sub('[hidden_phone]', result)
    result = _WHITESPACE_RE.sub(' ', result)
    return result.strip()


# ---------------------------------------------------------------------------
# Input length guard
# ---------------------------------------------------------------------------

def _truncate(text: str, max_chars: int | None = None) -> str:
    """Truncate text to max_chars (from settings if not given)."""
    if max_chars is None:
        max_chars = getattr(settings, 'AI_MAX_INPUT_CHARS', 2000)
    if not text:
        return ""
    return text[:max_chars]


# ---------------------------------------------------------------------------
# OpenAI-compatible HTTP client
# ---------------------------------------------------------------------------

def _call_llm_api(system_prompt: str, user_prompt: str) -> str | None:
    """
    Send a chat completion request to an OpenAI-compatible provider.
    Returns the generated text on success, or None on any failure.
    Never raises — all errors are caught and logged safely.
    """
    ai_key = getattr(settings, 'AI_API_KEY', '') or ''
    ai_url = getattr(settings, 'AI_API_URL', '') or ''
    ai_model = getattr(settings, 'AI_API_MODEL', '') or ''
    ai_timeout = getattr(settings, 'AI_TIMEOUT_SECONDS', 15)
    ai_max_tokens = getattr(settings, 'AI_MAX_OUTPUT_TOKENS', 500)
    ai_temperature = getattr(settings, 'AI_TEMPERATURE', 0.7)

    if not ai_key or not ai_url:
        logger.info("AI provider not configured (missing key or URL). Using fallback.")
        return None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ai_key}",
    }

    body = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": ai_temperature,
        "max_tokens": ai_max_tokens,
    }

    # Only include model field if configured — some local providers don't need it
    if ai_model:
        body["model"] = ai_model

    req = urllib.request.Request(
        ai_url,
        data=json.dumps(body).encode('utf-8'),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=ai_timeout) as response:
            raw = response.read().decode('utf-8')

        res_data = json.loads(raw)

        # Navigate standard OpenAI response shape
        choices = res_data.get('choices')
        if not choices or not isinstance(choices, list) or len(choices) == 0:
            logger.warning("AI provider returned empty choices array.")
            return None

        message = choices[0].get('message', {})
        content = message.get('content', '').strip()

        if not content:
            logger.warning("AI provider returned empty content.")
            return None

        return content

    except urllib.error.URLError as e:
        logger.error("AI provider network error: %s", type(e).__name__)
        return None
    except json.JSONDecodeError:
        logger.error("AI provider returned invalid JSON.")
        return None
    except (KeyError, IndexError, TypeError) as e:
        logger.error("AI provider response parsing error: %s", type(e).__name__)
        return None
    except Exception as e:
        # Catch-all: timeouts, socket errors, unexpected shapes
        logger.error("AI provider unexpected error: %s", type(e).__name__)
        return None


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_request_system_prompt(locale: str) -> str:
    return (
        "You are an AI assistant helping a client write a professional, clear event request description. "
        "Improve and expand the client's draft description. "
        "Output ONLY the improved description as plain text. "
        "Do not output conversational preamble, notes, HTML, or markdown formatting. "
        "Keep it professional, friendly, and structured. "
        f"Respond in the language matching locale: '{locale}'."
    )


def _build_request_user_prompt(category: str, city: str, event_date: str,
                                budget: str, draft: str) -> str:
    parts = []
    if category:
        parts.append(f"Category: {category}")
    if city:
        parts.append(f"City: {city}")
    if event_date:
        parts.append(f"Date: {event_date}")
    if budget:
        parts.append(f"Budget: {budget}")
    if draft:
        parts.append(f"Draft input: {draft}")
    return "\n".join(parts)


def _build_offer_system_prompt(locale: str) -> str:
    return (
        "You are an AI assistant helping a service provider write a professional, polite cover letter "
        "for an event request offer. Write a cover letter stating readiness to perform the services. "
        "Output ONLY the cover letter as plain text. "
        "Do not output conversational preamble, notes, HTML, or markdown formatting. "
        "Keep it professional, warm, and structured. "
        f"Respond in the language matching locale: '{locale}'."
    )


def _build_offer_user_prompt(request_description: str, service_title: str,
                              price: str) -> str:
    parts = []
    if request_description:
        parts.append(f"Request description: {request_description}")
    if service_title:
        parts.append(f"My service title: {service_title}")
    if price:
        parts.append(f"Offered price: {price}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public API — generate_request_suggestion
# ---------------------------------------------------------------------------

def generate_request_suggestion(category, city, event_date, budget, draft, locale):
    """Generate an improved event request description via LLM or fallback."""

    # Sanitize and truncate all user-supplied text
    category = _truncate(sanitize_text(str(category or '')))
    city = _truncate(sanitize_text(str(city or '')), 200)
    event_date = _truncate(str(event_date or ''), 50)
    budget = _truncate(sanitize_text(str(budget or '')), 100)
    draft = _truncate(sanitize_text(str(draft or '')))

    system_prompt = _build_request_system_prompt(locale)
    user_prompt = _build_request_user_prompt(category, city, event_date, budget, draft)

    suggestion = _call_llm_api(system_prompt, user_prompt)
    if suggestion:
        return suggestion, "llm"

    # ----- Fallback mode templates -----
    return _fallback_request(category, city, event_date, budget, draft, locale), "fallback"


def _fallback_request(category, city, event_date, budget, draft, locale):
    if locale == 'en':
        parts = ["Looking for a specialist in the Eventmate platform."]
        if category:
            parts.append(f"Category: {category}.")
        if city:
            parts.append(f"Location: {city}.")
        if event_date:
            parts.append(f"Scheduled date: {event_date}.")
        if budget:
            parts.append(f"Estimated budget: {budget} ₸.")
        if draft:
            parts.append(f"Description draft: {draft}")
        parts.append("Please send your proposals with pricing and portfolio links. Thank you!")
    elif locale == 'kz':
        parts = ["Eventmate платформасында маман іздеймін."]
        if category:
            parts.append(f"Санат: {category}.")
        if city:
            parts.append(f"Қала: {city}.")
        if event_date:
            parts.append(f"Жоспарланған күн: {event_date}.")
        if budget:
            parts.append(f"Жоспарланған бюджет: {budget} ₸.")
        if draft:
            parts.append(f"Жоба нұсқасы: {draft}")
        parts.append("Өтінемін, өз бағаларыңыз бен портфолио сілтемелеріңізді жіберіңіз. Рақмет!")
    else:  # 'ru'
        parts = ["Ищу специалиста на платформе Eventmate."]
        if category:
            parts.append(f"Категория услуг: {category}.")
        if city:
            parts.append(f"Город проведения: {city}.")
        if event_date:
            parts.append(f"Планируемая дата: {event_date}.")
        if budget:
            parts.append(f"Приблизительный бюджет: {budget} ₸.")
        if draft:
            parts.append(f"Черновик описания: {draft}")
        parts.append("Пожалуйста, направляйте ваши предложения с указанием стоимости и ссылками на портфолио. Спасибо!")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public API — generate_offer_suggestion
# ---------------------------------------------------------------------------

def generate_offer_suggestion(request_description, service_title, price, locale):
    """Generate a professional cover letter for a provider offer via LLM or fallback."""

    # Sanitize and truncate all user-supplied text
    request_description = _truncate(sanitize_text(str(request_description or '')))
    service_title = _truncate(sanitize_text(str(service_title or '')), 200)
    price = _truncate(sanitize_text(str(price or '')), 100)

    system_prompt = _build_offer_system_prompt(locale)
    user_prompt = _build_offer_user_prompt(request_description, service_title, price)

    suggestion = _call_llm_api(system_prompt, user_prompt)
    if suggestion:
        return suggestion, "llm"

    # ----- Fallback mode templates -----
    return _fallback_offer(request_description, service_title, price, locale), "fallback"


def _fallback_offer(request_description, service_title, price, locale):
    short_desc = request_description[:60] + "..." if len(request_description) > 60 else request_description

    if locale == 'en':
        parts = ["Hello! I am interested in your request."]
        if short_desc:
            parts.append(f"Regarding request: \"{short_desc}\"")
        if service_title:
            parts.append(f"I offer my service: \"{service_title}\".")
        if price:
            parts.append(f"My proposed price: {price} ₸.")
        parts.append("I have experience in this field and will ensure high quality. Let's discuss details!")
    elif locale == 'kz':
        parts = ["Сәлеметсіз бе! Сіздің тапсырысыңызға қызығушылық танытып отырмын."]
        if short_desc:
            parts.append(f"Тапсырыс бойынша: \"{short_desc}\"")
        if service_title:
            parts.append(f"Өз қызметімді ұсынамын: \"{service_title}\".")
        if price:
            parts.append(f"Менің ұсынатын бағам: {price} ₸.")
        parts.append("Осы салада тәжірибем бар және жоғары сапаны қамтамасыз етемін. Толығырақ талқылайық!")
    else:  # 'ru'
        parts = ["Здравствуйте! Заинтересован в вашем заказе."]
        if short_desc:
            parts.append(f"По заказу: \"{short_desc}\"")
        if service_title:
            parts.append(f"Предлагаю свою услугу: \"{service_title}\".")
        if price:
            parts.append(f"Моя стоимость: {price} ₸.")
        parts.append("Имею отличный опыт в данной сфере и гарантирую качественное выполнение. Буду рад сотрудничеству!")

    return "\n".join(parts)
