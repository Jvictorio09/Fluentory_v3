from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from myApp.models import CoursePurchase, PaymentTransaction, RefundRequest
from myApp.services.audit import write_audit_log

try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False


class BaseGateway:
    provider = "manual"

    def create_checkout(self, purchase, request=None):
        return {
            "status": "pending",
            "checkout_url": "",
            "provider_payment_id": "",
            "raw": {},
        }

    def refund(self, transaction, amount):
        return {
            "success": False,
            "provider_refund_id": "",
            "raw": {"error": "Refund not implemented for this provider"},
        }


class StripeGateway(BaseGateway):
    provider = "stripe"

    def create_checkout(self, purchase, request=None):
        if not STRIPE_AVAILABLE:
            return {"status": "failed", "checkout_url": "", "provider_payment_id": "", "raw": {"error": "stripe package missing"}}
        stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")
        success_url = request.build_absolute_uri("/my-dashboard/") if request else "http://localhost:8000/my-dashboard/"
        cancel_url = request.build_absolute_uri("/") if request else "http://localhost:8000/"
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": (purchase.currency or "USD").lower(),
                    "product_data": {"name": purchase.course.name},
                    "unit_amount": int(Decimal(purchase.amount) * 100),
                },
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"purchase_id": str(purchase.id)},
            client_reference_id=str(purchase.id),
        )
        return {
            "status": "pending",
            "checkout_url": session.url,
            "provider_payment_id": session.id,
            "raw": {"session_id": session.id},
        }

    def refund(self, transaction, amount):
        if not STRIPE_AVAILABLE:
            return {"success": False, "provider_refund_id": "", "raw": {"error": "stripe package missing"}}
        stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")
        refund = stripe.Refund.create(
            payment_intent=transaction.provider_payment_id,
            amount=int(Decimal(amount) * 100),
        )
        return {
            "success": True,
            "provider_refund_id": refund.id,
            "raw": {"refund_id": refund.id},
        }


class PayPalGateway(BaseGateway):
    provider = "paypal"

    def create_checkout(self, purchase, request=None):
        # Placeholder for full PayPal order API integration.
        return {
            "status": "pending",
            "checkout_url": f"/payments/paypal/start/{purchase.id}/",
            "provider_payment_id": f"paypal_order_{purchase.id}_{int(timezone.now().timestamp())}",
            "raw": {"mock": True},
        }

    def refund(self, transaction, amount):
        return {
            "success": True,
            "provider_refund_id": f"paypal_refund_{transaction.id}_{int(timezone.now().timestamp())}",
            "raw": {"mock": True, "amount": str(amount)},
        }


GATEWAYS = {
    "stripe": StripeGateway(),
    "paypal": PayPalGateway(),
}


def get_gateway(provider):
    return GATEWAYS.get((provider or "").lower(), BaseGateway())


def create_checkout_for_purchase(purchase, provider="stripe", request=None, idempotency_key=""):
    gateway = get_gateway(provider)
    result = gateway.create_checkout(purchase, request=request)
    txn = PaymentTransaction.objects.create(
        provider=gateway.provider,
        provider_payment_id=result.get("provider_payment_id", ""),
        idempotency_key=idempotency_key,
        purchase=purchase,
        user=purchase.user,
        amount=purchase.amount,
        currency=purchase.currency,
        status=result.get("status", "pending"),
        metadata=result.get("raw", {}),
    )
    write_audit_log(
        action="payment.checkout.created",
        actor=purchase.user,
        entity_type="CoursePurchase",
        entity_id=purchase.id,
        metadata={"provider": gateway.provider, "transaction_id": txn.id},
    )
    return result, txn


def request_refund(purchase, amount, actor=None, reason=""):
    txn = purchase.transactions.order_by("-created_at").first()
    refund = RefundRequest.objects.create(
        purchase=purchase,
        transaction=txn,
        requested_by=actor,
        amount=amount,
        reason=reason,
        status="requested",
    )
    write_audit_log(
        action="refund.requested",
        actor=actor,
        entity_type="CoursePurchase",
        entity_id=purchase.id,
        metadata={"refund_id": refund.id, "amount": str(amount), "reason": reason},
    )
    return refund


def process_refund(refund, actor=None):
    purchase = refund.purchase
    txn = refund.transaction or purchase.transactions.order_by("-created_at").first()
    gateway = get_gateway(txn.provider if txn else purchase.provider)
    response = gateway.refund(txn, refund.amount) if txn else {"success": False, "provider_refund_id": "", "raw": {"error": "No transaction found"}}
    if response.get("success"):
        refund.status = "processed"
        refund.provider_refund_id = response.get("provider_refund_id", "")
        refund.approved_by = actor
        refund.processed_at = timezone.now()
        refund.metadata = response.get("raw", {})
        refund.save()
        purchase.status = "refunded"
        purchase.save(update_fields=["status"])
        write_audit_log(
            action="refund.processed",
            actor=actor,
            entity_type="RefundRequest",
            entity_id=refund.id,
            metadata={"purchase_id": purchase.id, "provider_refund_id": refund.provider_refund_id},
        )
    else:
        refund.status = "failed"
        refund.metadata = response.get("raw", {})
        refund.save(update_fields=["status", "metadata"])
    return response

