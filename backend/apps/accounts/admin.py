from django.contrib import admin
from .models import ProviderProfile, Availability

@admin.register(ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_email', 'rating_avg', 'is_blocked')
    list_filter = ('is_blocked',)
    search_fields = ('user__email',)
    list_editable = ('is_blocked',)

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'

@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ('provider', 'start_at', 'end_at', 'status', 'order')
    list_filter = ('status', 'start_at')
    search_fields = ('provider__user__email',)
