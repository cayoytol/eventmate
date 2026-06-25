from django.contrib import admin
from .models import Chat, ChatMessage


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'provider', 'request', 'order', 'created_at']
    list_filter = ['created_at']
    search_fields = ['client__email', 'provider__user__email']
    raw_id_fields = ['client', 'provider', 'request', 'order']


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'chat', 'sender', 'content_preview', 'is_system', 'created_at']
    list_filter = ['is_system', 'created_at']
    search_fields = ['content', 'sender__email']
    raw_id_fields = ['chat', 'sender']
    
    def content_preview(self, obj):
        return obj.content[:50]
    content_preview.short_description = 'Content'
