from django.db import models
from django.conf import settings


class Chat(models.Model):
    """1-on-1 chat between client and provider for a targeted request"""
    request = models.ForeignKey(
        'marketplace.EventRequest',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='chats'
    )
    order = models.OneToOneField(
        'marketplace.Order',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='chat'
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='client_chats'
    )
    provider = models.ForeignKey(
        'accounts.ProviderProfile',
        on_delete=models.CASCADE,
        related_name='provider_chats'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        constraints = [
            # One chat per targeted request
            models.UniqueConstraint(
                fields=['request'],
                name='unique_chat_per_request'
            )
        ]
    
    def __str__(self):
        return f"Chat {self.id}: {self.client.email} ↔ {self.provider.user.email}"


class ChatMessage(models.Model):
    """Individual message in a chat"""
    chat = models.ForeignKey(
        Chat,
        related_name='messages',
        on_delete=models.CASCADE
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,  # null = system message
        blank=True,
        on_delete=models.SET_NULL,
        related_name='sent_messages'
    )
    content = models.TextField(blank=True)
    attachment_url = models.URLField(blank=True)
    is_system = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        sender_name = self.sender.email if self.sender else "System"
        return f"[{self.chat_id}] {sender_name}: {self.content[:30]}"
