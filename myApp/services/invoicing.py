from django.utils import timezone

from myApp.models import Invoice


def issue_invoice_for_purchase(purchase):
    """Create or return an invoice for a paid purchase."""
    if not purchase:
        return None
    invoice, _ = Invoice.objects.get_or_create(
        purchase=purchase,
        defaults={
            "invoice_number": f"INV-{timezone.now().strftime('%Y%m%d')}-{purchase.id}",
            "amount": purchase.amount,
            "currency": purchase.currency,
            "payload": {
                "user_id": purchase.user_id,
                "course_id": purchase.course_id,
                "provider": purchase.provider,
                "provider_id": purchase.provider_id,
            },
        },
    )
    return invoice

