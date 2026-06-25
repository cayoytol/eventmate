import django_filters
from .models import Service


class ServiceFilter(django_filters.FilterSet):
    price_min = django_filters.NumberFilter(field_name="price_amount", lookup_expr="gte")
    price_max = django_filters.NumberFilter(field_name="price_amount", lookup_expr="lte")
    category_slug = django_filters.CharFilter(field_name="category__slug")
    category_id = django_filters.NumberFilter(field_name="category__id")
    city = django_filters.CharFilter(field_name="city", lookup_expr="icontains")
    provider = django_filters.CharFilter(method="filter_provider")

    class Meta:
        model = Service
        fields = ["city", "price_type", "is_active", "category_id"]

    def filter_provider(self, queryset, name, value):
        if value == "me":
            request = getattr(self, "request", None)
            if not request or not request.user or not request.user.is_authenticated:
                return queryset.none()
            if getattr(request.user, "role", None) == "provider":
                try:
                    return queryset.filter(provider=request.user.provider_profile)
                except Exception:
                    return queryset.none()
            return queryset.none()
        else:
            try:
                provider_id = int(value)
                return queryset.filter(provider_id=provider_id)
            except ValueError:
                return queryset.none()
