from apps.catalog.models import Service
from apps.accounts.models import ProviderProfile

# Get all services
all_services = Service.objects.all()
print(f"\n=== TOTAL SERVICES IN DB: {all_services.count()} ===\n")

for s in all_services:
    provider_info = f"Provider: {s.provider}" if s.provider else "Provider: NULL"
    print(f"ID={s.id} | Title='{s.title}' | Active={s.is_active} | {provider_info}")

# Check active services
active = Service.objects.filter(is_active=True)
print(f"\n=== ACTIVE SERVICES: {active.count()} ===\n")

# Check services with NULL provider
null_provider = Service.objects.filter(provider__isnull=True)
print(f"\n=== SERVICES WITH NULL PROVIDER: {null_provider.count()} ===")
for s in null_provider:
    print(f"  ID={s.id} | Title='{s.title}' | Active={s.is_active}")
