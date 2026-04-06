from django.utils import timezone

from myApp.models import EmailSequenceRule, EmailSequenceLog


def queue_sequence(trigger_key, user=None, payload=None):
    payload = payload or {}
    rule = EmailSequenceRule.objects.filter(trigger_key=trigger_key, is_active=True).first()
    return EmailSequenceLog.objects.create(
        rule=rule,
        user=user,
        payload=payload,
        status="queued",
    )


def process_due_sequences():
    now = timezone.now()
    due = EmailSequenceLog.objects.filter(status="queued")
    processed = 0
    for log in due.select_related("rule"):
        if log.rule and log.rule.delay_minutes > 0:
            age_minutes = (now - log.created_at).total_seconds() / 60
            if age_minutes < log.rule.delay_minutes:
                continue
        log.status = "sent"
        log.sent_at = now
        log.save(update_fields=["status", "sent_at"])
        processed += 1
    return processed

