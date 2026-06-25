from django.contrib import admin
from .models import Notification

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'type', 'is_read', 'created_at')
    list_filter = ('type', 'is_read', 'created_at')
    search_fields = ('user__email', 'payload')
    readonly_fields = ('user', 'type', 'payload', 'is_read', 'created_at')
    
    def has_add_permission(self, request):
        return False
