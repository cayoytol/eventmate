from django.core.management.base import BaseCommand
from apps.billing.models import Plan


class Command(BaseCommand):
    help = 'Seed default subscription plans'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force overwrite prices and limits to default canonical configurations',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        
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
            code = p_data['code']
            try:
                plan = Plan.objects.get(code=code)
                if force:
                    for key, val in p_data.items():
                        setattr(plan, key, val)
                    plan.save()
                    action = "Overwrote"
                else:
                    updated = False
                    for key, val in p_data.items():
                        if key in ['price', 'duration_days', 'limits_json']:
                            continue
                        if not getattr(plan, key):
                            setattr(plan, key, val)
                            updated = True
                    if updated:
                        plan.save()
                        action = "Updated empty fields on"
                    else:
                        action = "Preserved"
            except Plan.DoesNotExist:
                plan = Plan.objects.create(**p_data)
                action = "Created"

            self.stdout.write(
                self.style.SUCCESS(f'{action} plan: {plan.name_en} ({plan.code}) (KZT {plan.price})')
            )

        self.stdout.write(self.style.SUCCESS('Plans seeded successfully'))
