from .models import Notification

def create_notification(user, title, message, n_type, metadata=None):
    """Helper to create a notification"""
    if metadata is None:
        metadata = {}
        
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        type=n_type,
        payload=metadata
    )
