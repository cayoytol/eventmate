from django.core.management.base import BaseCommand
from apps.catalog.models import Category


class Command(BaseCommand):
    help = 'Seed initial categories for EventMate'

    def handle(self, *args, **kwargs):
        categories_data = [
            {
                'name_ru': 'Музыка',
                'name_en': 'Music',
                'name_kz': 'Музыка',
                'slug': 'music',
            },
            {
                'name_ru': 'Фотография',
                'name_en': 'Photography',
                'name_kz': 'Фотография',
                'slug': 'photography',
            },
            {
                'name_ru': 'Видеосъёмка',
                'name_en': 'Videography',
                'name_kz': 'Бейнефильм',
                'slug': 'videography',
            },
            {
                'name_ru': 'Кейтеринг',
                'name_en': 'Catering',
                'name_kz': 'Тамақтандыру',
                'slug': 'catering',
            },
            {
                'name_ru': 'Декор',
                'name_en': 'Decoration',
                'name_kz': 'Сәндеу',
                'slug': 'decoration',
            },
            {
                'name_ru': 'Ведущий',
                'name_en': 'Host/MC',
                'name_kz': 'Жүргізуші',
                'slug': 'host',
            },
            {
                'name_ru': 'Площадка',
                'name_en': 'Venue',
                'name_kz': 'Алаң',
                'slug': 'venue',
            },
            {
                'name_ru': 'Транспорт',
                'name_en': 'Transportation',
                'name_kz': 'Көлік',
                'slug': 'transportation',
            },
        ]

        created_count = 0
        for cat_data in categories_data:
            category, created = Category.objects.get_or_create(
                slug=cat_data['slug'],
                defaults=cat_data
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created: {category.name_en}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Already exists: {category.name_en}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\n🎉 Done! Created {created_count} new categories.')
        )
