from outreach_system.config import get_settings
from outreach_system.integrations.easybroker import EasyBrokerClient


def fetch_contacts_paginated(days_back: int = 0):
    client = EasyBrokerClient(get_settings())
    contacts = client.fetch_contacts(days_back=days_back)
    yield [contact.model_dump(mode="json") for contact in contacts]


def fetch_all_contacts(days_back: int = 0) -> list[dict]:
    return [contact for page in fetch_contacts_paginated(days_back=days_back) for contact in page]


def parse_contact(raw: dict) -> dict:
    return raw


def get_parsed_contacts(days_back: int = 0) -> list[dict]:
    return fetch_all_contacts(days_back=days_back)
