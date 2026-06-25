from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.marketplace.models import EventRequest, Order
from .models import Chat, ChatMessage


@receiver(post_save, sender=EventRequest)
def create_chat_on_targeted_request(sender, instance, created, **kwargs):
    """Auto-create chat when targeted request is created"""
    if not created:
        return
    
    # Only for targeted requests
    if not instance.target_provider or not instance.target_service:
        return
    
    # Create chat (get_or_create to handle race conditions)
    chat, chat_created = Chat.objects.get_or_create(
        request=instance,
        defaults={
            'client': instance.client,
            'provider': instance.target_provider
        }
    )
    
    if chat_created:
        # Add system message
        ChatMessage.objects.create(
            chat=chat,
            sender=None,
            content=f"Заявка создана по услуге: {instance.target_service.title}",
            is_system=True
        )


@receiver(post_save, sender=Order)
def link_chat_to_order(sender, instance, created, **kwargs):
    """Link existing chat to order when created"""
    if not created:
        return
    
    # Find chat by request
    try:
        chat = Chat.objects.get(
            request=instance.offer.request,
            provider=instance.provider_profile,
            client=instance.client
        )
        
        # Link order
        chat.order = instance
        chat.save(update_fields=['order', 'updated_at'])
        
        # Add system message
        ChatMessage.objects.create(
            chat=chat,
            sender=None,
            content=f"Сделка подтверждена. Заказ #{instance.id} создан.",
            is_system=True
        )
    except Chat.DoesNotExist:
        # Edge case: chat doesn't exist (shouldn't happen for targeted requests)
        pass
