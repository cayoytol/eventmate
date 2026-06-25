from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'provider_profile', 'amount', 'currency', 'status', 'created_at', 'paid_at')
    list_filter = ('status', 'currency')
    search_fields = ('provider_profile__user__email',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'paid_at')
