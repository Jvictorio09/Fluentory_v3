from myApp.models import AuditLog


SENSITIVE_ACTIONS = {
    "refund.requested",
    "refund.approved",
    "access.granted",
    "access.revoked",
    "role.partner.assigned",
    "role.teacher.assigned",
}


def write_audit_log(action, actor=None, entity_type="", entity_id="", metadata=None):
    metadata = metadata or {}
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else "",
        metadata=metadata,
    )

