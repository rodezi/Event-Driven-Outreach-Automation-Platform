from __future__ import annotations

from outreach_system.exceptions import EmailDeliveryError
from outreach_system.models import EmailState, StoredContact
from outreach_system.services.outreach import OutreachService


class FakeRepository:
    def __init__(self, contacts: list[StoredContact]) -> None:
        self.contacts = contacts
        self.processing: list[int] = []
        self.sent: list[tuple[int, str]] = []
        self.failed: list[tuple[int, str]] = []
        self.invalid: list[int] = []
        self.limit_requested: int | None = None

    def get_pending_contacts(self, limit: int | None = None) -> list[StoredContact]:
        self.limit_requested = limit
        return self.contacts[:limit] if limit is not None else self.contacts

    def mark_as_processing(self, row_index: int) -> None:
        self.processing.append(row_index)

    def mark_as_sent(self, row_index: int, resend_id: str) -> None:
        self.sent.append((row_index, resend_id))

    def mark_as_failed(self, row_index: int, error_message: str) -> None:
        self.failed.append((row_index, error_message))

    def mark_as_invalid(self, row_index: int) -> None:
        self.invalid.append(row_index)


class FakeEmailClient:
    def __init__(self, results: list[object]) -> None:
        self.results = results
        self.sent_contacts: list[str] = []
        self.waits = 0

    def send_email(self, contact: StoredContact):
        self.sent_contacts.append(contact.external_id)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def wait_before_next_send(self) -> None:
        self.waits += 1


def _contact(
    external_id: str,
    *,
    row_index: int,
    email: str | None = "lead@example.com",
    state: EmailState = EmailState.PENDING,
) -> StoredContact:
    return StoredContact(
        external_id=external_id,
        row_index=row_index,
        email=email,
        email_state=state,
    )


def test_does_not_send_contacts_already_sent() -> None:
    repository = FakeRepository([_contact("1", row_index=2, state=EmailState.SENT)])
    email_client = FakeEmailClient([])

    summary = OutreachService(repository, email_client).send_pending_emails(max_emails=10)

    assert summary.emails_sent == 0
    assert email_client.sent_contacts == []


def test_does_not_send_contacts_with_invalid_email() -> None:
    repository = FakeRepository([_contact("1", row_index=2, email=None)])
    email_client = FakeEmailClient([])

    summary = OutreachService(repository, email_client).send_pending_emails(max_emails=10)

    assert summary.email_failures == 1
    assert repository.invalid == [2]


def test_marks_contact_as_sent_after_success() -> None:
    repository = FakeRepository([_contact("1", row_index=2)])
    email_client = FakeEmailClient([
        type(
            "Result",
            (),
            {"state": EmailState.SENT, "resend_id": "re_123", "error_message": None},
        )()
    ])

    summary = OutreachService(repository, email_client).send_pending_emails(max_emails=10)

    assert summary.emails_sent == 1
    assert repository.processing == [2]
    assert repository.sent == [(2, "re_123")]


def test_marks_contact_as_failed_after_error() -> None:
    repository = FakeRepository([_contact("1", row_index=2)])
    email_client = FakeEmailClient([EmailDeliveryError("provider failed")])

    summary = OutreachService(repository, email_client).send_pending_emails(max_emails=10)

    assert summary.email_failures == 1
    assert repository.failed


def test_max_emails_is_forwarded_to_repository() -> None:
    repository = FakeRepository(
        [_contact("1", row_index=2), _contact("2", row_index=3), _contact("3", row_index=4)]
    )
    email_client = FakeEmailClient(
        [
            type(
                "Result",
                (),
                {"state": EmailState.SENT, "resend_id": "re_1", "error_message": None},
            )(),
            type(
                "Result",
                (),
                {"state": EmailState.SENT, "resend_id": "re_2", "error_message": None},
            )(),
        ]
    )

    summary = OutreachService(repository, email_client).send_pending_emails(max_emails=2)

    assert repository.limit_requested == 2
    assert summary.emails_sent == 2
