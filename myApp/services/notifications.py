from django.utils import timezone

from myApp.models import NotificationEvent, NotificationTemplate
from myApp.utils.email import send_gift_email


def queue_notification(event_key, user=None, payload=None):
    payload = payload or {}
    return NotificationEvent.objects.create(
        event_key=event_key,
        user=user,
        payload=payload,
        status="pending",
    )


def render_template(template, payload):
    subject = (template.subject_template or "").format(**payload)
    body = (template.body_template or "").format(**payload)
    return subject, body


def process_notification_event(event):
    template = NotificationTemplate.objects.filter(event_key=event.event_key, channel="email", is_active=True).first()
    if not template:
        event.status = "failed"
        event.processed_at = timezone.now()
        event.save(update_fields=["status", "processed_at"])
        return {"success": False, "error": "No template configured"}
    # Existing project already uses Resend via helper in utils.email.
    if event.event_key == "gift.sent" and event.payload.get("gift_id"):
        from myApp.models import GiftPurchase
        gift = GiftPurchase.objects.filter(id=event.payload["gift_id"]).first()
        if gift:
            result = send_gift_email(gift)
            event.status = "processed" if result.get("success") else "failed"
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "processed_at"])
            return result
    event.status = "processed"
    event.processed_at = timezone.now()
    event.save(update_fields=["status", "processed_at"])
    return {"success": True}

