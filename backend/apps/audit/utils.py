from .models import AuditLog

def log_action(actor, action, target_type, target_id=None, ip_address=None, details_json=None):
    if details_json is None:
        details_json = {}
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        ip_address=ip_address,
        details_json=details_json
    )

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
