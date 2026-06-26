import pytest

from outreach_system.config import Settings
from outreach_system.exceptions import ConfigurationError


def test_config_validates_delay_range() -> None:
    with pytest.raises(ConfigurationError):
        Settings.model_validate(
            {
                "EASYBROKER_API_KEY": "easybroker-test-key",
                "GOOGLE_SERVICE_ACCOUNT_JSON": '{"type":"service_account"}',
                "GOOGLE_SPREADSHEET_ID": "spreadsheet-id",
                "RESEND_API_KEY": "resend-test-key",
                "RESEND_FROM_EMAILS": ["ops@example.com"],
                "EMAIL_DELAY_MIN_SECONDS": 10,
                "EMAIL_DELAY_MAX_SECONDS": 5,
            }
        )
