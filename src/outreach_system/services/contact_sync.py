from __future__ import annotations

from outreach_system.integrations.easybroker import EasyBrokerClient
from outreach_system.integrations.google_sheets import ContactRepository
from outreach_system.models import ContactSyncResult


class ContactSyncService:
    def __init__(self, easybroker_client: EasyBrokerClient, repository: ContactRepository) -> None:
        self._easybroker_client = easybroker_client
        self._repository = repository

    def sync(self) -> ContactSyncResult:
        contacts = self._easybroker_client.fetch_contacts()
        new_contacts, duplicates = self._repository.upsert_new_contacts(contacts)
        return ContactSyncResult(
            fetched_contacts=len(contacts),
            normalized_contacts=len(contacts),
            new_contacts=new_contacts,
            duplicate_contacts=duplicates,
        )
