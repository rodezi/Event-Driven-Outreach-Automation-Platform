import logging

import dns.resolver

from outreach_system.config import get_settings
from outreach_system.integrations.google_sheets import GoogleSheetsContactRepository
from outreach_system.logging_config import configure_logging

logger = logging.getLogger(__name__)


def has_mx_record(email: str) -> bool:
    try:
        domain = email.split("@", 1)[1].strip()
        dns.resolver.resolve(domain, "MX", lifetime=5)
        return True
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return False
    except Exception:
        return True


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    repository = GoogleSheetsContactRepository(settings)
    rows = repository.get_pending_contacts()
    for row in rows:
        if row.row_index is None:
            continue
        if row.email is None or not has_mx_record(str(row.email)):
            repository.mark_as_invalid(row.row_index)
            logger.info("Marked contact as invalid external_id=%s", row.external_id)


if __name__ == "__main__":
    main()
