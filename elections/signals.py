from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.core.serializers.json import DjangoJSONEncoder
import json
from .models import ResultAuditLog
from .middleware import get_current_user

# List of models we want to track automatically
TRACKED_MODELS = [
    'BureauDeVote', 'StationResult', 'ListResult', 
    'ElectionList', 'Election', 'CustomUser', 'RoleProfile', 'Commune', 'Wilaya'
]

def serialize_instance(instance):
    """Converts a Django model instance into a JSON-safe dictionary"""
    if not instance: return {}
    data = {}
    for field in instance._meta.fields:
        val = getattr(instance, field.attname)
        data[field.name] = val
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))

@receiver(pre_save)
def capture_old_values(sender, instance, **kwargs):
    if sender.__name__ in ['ResultAuditLog', 'Session']: return
    if sender.__name__ in TRACKED_MODELS:
        if instance.pk:
            try:
                old_instance = sender.objects.get(pk=instance.pk)
                instance._old_values = serialize_instance(old_instance)
                # 🕵️‍♂️ Track if it was previously NOT deleted
                instance._was_deleted = getattr(old_instance, 'is_deleted', False)
            except sender.DoesNotExist:
                instance._old_values = None
                instance._was_deleted = False

@receiver(post_save)
def log_save(sender, instance, created, **kwargs):
    if sender.__name__ in ['ResultAuditLog', 'Session']: return
    if sender.__name__ in TRACKED_MODELS:
        user = get_current_user()
        
        # 🕵️‍♂️ Detect Soft-Deletes
        is_now_deleted = getattr(instance, 'is_deleted', False)
        was_deleted = getattr(instance, '_was_deleted', False)
        
        if is_now_deleted and not was_deleted:
            action = 'delete'
            notes = f"حذف (Soft Delete) {sender.__name__} رقم {instance.pk}"
        elif created:
            action = 'create'
            notes = f"إضافة {sender.__name__} رقم {instance.pk}"
        else:
            action = 'update'
            notes = f"تعديل {sender.__name__} رقم {instance.pk}"
            
        ResultAuditLog.objects.create(
            table_name=sender.__name__,
            record_id=str(instance.pk),
            action=action,
            changed_by=user,
            old_values=getattr(instance, '_old_values', None),
            new_values=serialize_instance(instance),
            notes=notes
        )

@receiver(post_delete)
def log_hard_delete(sender, instance, **kwargs):
    """Fires only if you permanently delete from Django Admin"""
    if sender.__name__ in ['ResultAuditLog', 'Session']: return
    if sender.__name__ in TRACKED_MODELS:
        user = get_current_user()
        ResultAuditLog.objects.create(
            table_name=sender.__name__,
            record_id=str(instance.pk),
            action='delete',
            changed_by=user,
            old_values=serialize_instance(instance),
            new_values=None,
            notes=f"حذف نهائي (Hard Delete) {sender.__name__} رقم {instance.pk}"
        )