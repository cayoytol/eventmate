import logging
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.db import transaction
from apps.core.media import safe_delete_storage_object

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_delete, sender=User, dispatch_uid="cleanup_user_avatar_file_signal")
def cleanup_user_avatar_file(sender, instance, **kwargs):
    """
    Deletes the exact user avatar file from storage after database deletion commits.
    """
    if instance.avatar and instance.avatar.name:
        avatar_name = instance.avatar.name
        storage = instance.avatar.storage

        def delete_file():
            safe_delete_storage_object(storage, avatar_name, context="user_avatar_post_delete")

        transaction.on_commit(delete_file)
