from django.contrib import admin
from .models import ServiceComment

@admin.register(ServiceComment)
class ServiceCommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'service', 'user', 'short_text', 'parent', 'is_deleted', 'created_at')
    list_filter = ('is_deleted', 'created_at', 'service')
    search_fields = ('text', 'user__email', 'service__title')
    readonly_fields = ('created_at', 'updated_at')

    def short_text(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
