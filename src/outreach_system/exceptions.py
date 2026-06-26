class OutreachError(Exception):
    """Base application error."""


class ConfigurationError(OutreachError):
    """Raised when required configuration is missing or invalid."""


class EasyBrokerAPIError(OutreachError):
    """Raised for EasyBroker API failures."""


class SheetsError(OutreachError):
    """Raised for Google Sheets failures."""


class EmailDeliveryError(OutreachError):
    """Raised when the email provider rejects or fails a send."""


class WebhookVerificationError(OutreachError):
    """Raised when a webhook signature cannot be verified."""
