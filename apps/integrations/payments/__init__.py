def get_payment_provider(name: str):
    if name == "liqpay":
        from .liqpay import LiqPayProvider
        return LiqPayProvider()
    elif name == "wayforpay":
        from .wayforpay import WayForPayProvider
        return WayForPayProvider()
    elif name == "monobank":
        from .monobank import MonobankProvider
        return MonobankProvider()
    raise ValueError(f"Unknown payment provider: {name}")
