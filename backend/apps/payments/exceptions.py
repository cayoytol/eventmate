class PaymentProviderError(Exception):
    """Base exception for all payment provider operations"""
    pass


class PaymentProviderConfigurationError(PaymentProviderError):
    """Raised when a payment provider is selected but misconfigured or credentials are missing"""
    pass


class PaymentProviderResponseError(PaymentProviderError):
    """Raised when a payment provider returns a terminal or structured error response"""
    pass


class PaymentProviderTemporaryError(PaymentProviderError):
    """Raised when a payment provider fails due to a transient API or network issue"""
    pass
