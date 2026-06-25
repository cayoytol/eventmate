"""
Temporary script to seed billing plans directly (bypasses Django system checks).
Run: venv\Scripts\python seed_plans_local.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.billing.models import Plan  # noqa: E402

plans_data = [
    {
        'code': 'free',
        'name_ru': 'Бесплатный',
        'name_en': 'Free',
        'name_kz': 'Тегін',
        'price': 0,
        'duration_days': 3650,
        'limits_json': {'max_active_services': 3, 'offers_per_month': 10, 'max_portfolio_items': 10},
        'sort_order': 0,
        'is_active': True,
        'description_ru': 'Базовый тариф с ограниченными лимитами.',
        'description_en': 'Basic plan with limited capacity.',
        'description_kz': 'Шектеулі лимиттері бар негізгі тариф.',
    },
    {
        'code': 'pro',
        'name_ru': 'Про',
        'name_en': 'Pro',
        'name_kz': 'Про',
        'price': 9900,
        'duration_days': 30,
        'limits_json': {'max_active_services': 20, 'offers_per_month': 9999, 'max_portfolio_items': 50, 'analytics': True, 'ai_features': True},
        'sort_order': 1,
        'is_active': True,
        'description_ru': 'Продвинутый тариф для профессиональных исполнителей.',
        'description_en': 'Advanced plan for professional providers.',
        'description_kz': 'Кәсіби орындаушыларға арналған кеңейтілген тариф.',
    },
    {
        'code': 'enterprise',
        'name_ru': 'Энтерпрайз',
        'name_en': 'Enterprise',
        'name_kz': 'Энтерпрайз',
        'price': 49900,
        'duration_days': 30,
        'limits_json': {'max_active_services': 9999, 'offers_per_month': 9999, 'max_portfolio_items': 9999, 'analytics': True, 'ai_features': True, 'featured_placement': True},
        'sort_order': 2,
        'is_active': True,
        'description_ru': 'Максимальные лимиты и приоритетная поддержка для агентств.',
        'description_en': 'Maximum limits and priority support for agencies.',
        'description_kz': 'Агенттіктерге арналған максималды лимиттер мен басымдықты қолдау.',
    },
]

for p_data in plans_data:
    obj, created = Plan.objects.get_or_create(code=p_data['code'], defaults=p_data)
    status = 'Created' if created else 'Already exists'
    print(f"{status}: {obj.name_en} ({obj.code}) — {obj.price} KZT")

print('\nPlans seeded successfully!')
