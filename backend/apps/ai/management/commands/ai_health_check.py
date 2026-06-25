import urllib.request
import json
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.ai import services

class Command(BaseCommand):
    help = 'Run secure diagnostics on the AI integration'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Starting secure AI diagnostics..."))

        provider = getattr(settings, 'AI_PROVIDER', 'generic_openai_compatible')
        ai_key = getattr(settings, 'AI_API_KEY', '') or ''
        ai_url = getattr(settings, 'AI_API_URL', '') or ''
        ai_model = getattr(settings, 'AI_API_MODEL', '') or ''
        ai_timeout = getattr(settings, 'AI_TIMEOUT_SECONDS', 15)

        key_configured = bool(ai_key)
        url_configured = bool(ai_url)

        self.stdout.write(f"AI Provider: {provider}")
        self.stdout.write(f"AI Model: {ai_model or 'Not configured (using default)'}")
        self.stdout.write(f"AI URL Configured: {url_configured}")
        self.stdout.write(f"AI Key Configured: {key_configured}")

        if not key_configured or not url_configured:
            self.stdout.write(self.style.ERROR("Diagnostics Completed: AI is NOT fully configured (using fallback mode)."))
            return

        # Perform a safe diagnostic network request
        # Uses a generic greeting with system prompt to ensure end-to-end flow works.
        # We never print the key or any private headers or user prompts.
        self.stdout.write("Sending secure test request to AI provider...")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ai_key}",
        }
        body = {
            "messages": [
                {"role": "system", "content": "You are a health check assistant. Respond only with the word 'OK'."},
                {"role": "user", "content": "Ping"},
            ],
            "max_tokens": 50,
            "temperature": 0.0,
        }
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
            
            choices = res_data.get('choices', [])
            if choices and isinstance(choices, list) and len(choices) > 0:
                content = choices[0].get('message', {}).get('content', '').strip()
                if content:
                    self.stdout.write(self.style.SUCCESS(f"Connectivity Success: True (Response: '{content}')"))
                    self.stdout.write(self.style.SUCCESS("Diagnostics Completed: AI integration is fully functional!"))
                    return
            
            self.stdout.write(self.style.ERROR("Connectivity Success: False (Invalid response shape from provider)"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Connectivity Success: False (Error: {type(e).__name__})"))
            
        self.stdout.write(self.style.ERROR("Diagnostics Completed with issues."))
