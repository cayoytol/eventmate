import logging
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.db import transaction
from apps.core.media import safe_delete_storage_object
from .models import ServiceMedia

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=ServiceMedia, dispatch_uid="cleanup_service_media_file_signal")
def cleanup_service_media_file(sender, instance, **kwargs):
    """
    Deletes the exact uploaded storage object after database deletion commits.
    """
    if instance.file and instance.file.name:
        file_name = instance.file.name
        storage = instance.file.storage

        def delete_file():
            safe_delete_storage_object(storage, file_name, context="service_media_post_delete")

        transaction.on_commit(delete_file)
