"""Payment gateway factory."""

from app.core.protocols import PaymentGateway


def get_gateway(name: str) -> PaymentGateway:
    """Return a payment gateway instance by name."""
    if name == "stripe":
        from app.payments.gateways.stripe import StripeGateway
        return StripeGateway()
    elif name == "paystack":
        from app.payments.gateways.paystack import PaystackGateway
        return PaystackGateway()
    elif name == "flutterwave":
        from app.payments.gateways.flutterwave import FlutterwaveGateway
        return FlutterwaveGateway()
    raise ValueError(f"Unknown payment gateway: {name}")
