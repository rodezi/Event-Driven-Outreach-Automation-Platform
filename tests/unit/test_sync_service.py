from outreach_system.models import Contact
from outreach_system.services.contact_sync import ContactSyncService


class FakeEasyBrokerClient:
    def __init__(self, contacts: list[Contact]) -> None:
        self._contacts = contacts

    def fetch_contacts(self):
        return self._contacts


class FakeRepository:
    def __init__(self) -> None:
        self.saved: list[Contact] = []

    def upsert_new_contacts(self, contacts: list[Contact]) -> tuple[int, int]:
        self.saved.extend(contacts)
        seen: set[str] = set()
        duplicates = 0
        new_contacts = 0
        for contact in contacts:
            if contact.external_id in seen:
                duplicates += 1
            else:
                new_contacts += 1
                seen.add(contact.external_id)
        return new_contacts, duplicates


def test_sync_deduplicates_by_external_id() -> None:
    contacts = [
        Contact(external_id="1", email="one@example.com"),
        Contact(external_id="1", email="duplicate@example.com"),
        Contact(external_id="2", email="two@example.com"),
    ]
    service = ContactSyncService(FakeEasyBrokerClient(contacts), FakeRepository())

    result = service.sync()

    assert result.fetched_contacts == 3
    assert result.new_contacts == 2
    assert result.duplicate_contacts == 1
