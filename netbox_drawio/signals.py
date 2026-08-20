from core.models.object_types import ObjectType
from django.db import connection
from django.db.models.signals import post_migrate, pre_delete
from django.dispatch import receiver

from netbox_drawio.constants import PRE_DELETE_SKIPPED_APPS
from netbox_drawio.models import Diagram, DiagramAssignment

# None = unknown; resolved once per process, refreshed after each migrate run
_assignment_table_ready = None


def _assignment_table_exists():
    """
    Whether the DiagramAssignment table exists yet. During `manage.py migrate`, other
    apps' data migrations may delete rows before this plugin's migrations have run;
    on PostgreSQL a query against the missing table would not only fail but poison
    the surrounding transaction, so the receiver must not touch it at all.
    """
    global _assignment_table_ready
    if _assignment_table_ready is None:
        _assignment_table_ready = DiagramAssignment._meta.db_table in connection.introspection.table_names()
    return _assignment_table_ready


@receiver(post_migrate, dispatch_uid="netbox_drawio.reset_assignment_table_cache")
def reset_assignment_table_cache(sender, **kwargs):
    global _assignment_table_ready
    _assignment_table_ready = None


@receiver(pre_delete, dispatch_uid="netbox_drawio.pre_delete_receiver")
def pre_delete_receiver(sender, instance, **kwargs):
    """
    When a NetBox object is deleted, remove all of its diagram assignments.
    Diagrams themselves are not deleted; they persist until explicitly removed.
    """
    # Skip if the sender is one of our own models (avoid recursion)
    if sender in (Diagram, DiagramAssignment):
        return
    # Skip high-frequency Django internal models
    if sender._meta.app_label in PRE_DELETE_SKIPPED_APPS:
        return
    # Skip while our table does not exist (mid-migrate deletes from other apps)
    if not _assignment_table_exists():
        return

    try:
        object_type = ObjectType.objects.get_for_model(instance)
    except ObjectType.DoesNotExist:
        return

    try:
        # Delete the assignments for this object; diagrams are left intact
        DiagramAssignment.objects.filter(object_type_id=object_type.id, object_id=instance.pk).delete()
    except (TypeError, ValueError):
        # instance.pk is not an integer type — no assignments can exist for it
        return
