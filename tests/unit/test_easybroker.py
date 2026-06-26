from __future__ import annotations

from datetime import datetime

from outreach_system.integrations.easybroker import EasyBrokerClient


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("http error")


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def get(self, url: str, *, headers: dict[str, str], params: dict[str, object], timeout: int):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "params": dict(params),
                "timeout": timeout,
            }
        )
        return self.responses.pop(0)


def test_easybroker_pagination(settings) -> None:
    session = FakeSession(
        [
            FakeResponse(
                {
                    "content": [{"id": 1, "email": "one@example.com"}],
                    "pagination": {"next_page": True},
                }
            ),
            FakeResponse(
                {
                    "content": [{"id": 2, "email": "two@example.com"}],
                    "pagination": {"next_page": False},
                }
            ),
        ]
    )
    client = EasyBrokerClient(settings, session=session, sleeper=lambda _: None)

    contacts = client.fetch_contacts()

    assert [contact.external_id for contact in contacts] == ["1", "2"]
    assert [call["params"]["page"] for call in session.calls] == [1, 2]


def test_easybroker_uses_mexico_midnight_filter(settings) -> None:
    client = EasyBrokerClient(settings, session=FakeSession([]), sleeper=lambda _: None)

    updated_after = client._updated_after_filter(days_back=0)

    dt = datetime.fromisoformat(updated_after)
    assert dt.hour == 0
    assert dt.minute == 0
    assert dt.tzinfo is not None
