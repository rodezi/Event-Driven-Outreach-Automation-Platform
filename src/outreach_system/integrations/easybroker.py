from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Protocol

import requests

from outreach_system.config import Settings
from outreach_system.exceptions import EasyBrokerAPIError
from outreach_system.models import Contact

logger = logging.getLogger(__name__)


class HttpRequester(Protocol):
    def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, object],
        timeout: int,
    ) -> requests.Response: ...


class EasyBrokerClient:
    base_url = "https://api.easybroker.com/v1"

    def __init__(
        self,
        settings: Settings,
        session: HttpRequester | None = None,
        sleeper: callable | None = None,
    ) -> None:
        self._settings = settings
        self._session = session or requests.Session()
        self._sleep = sleeper or time.sleep

    def fetch_contacts(self, *, days_back: int | None = None) -> list[Contact]:
        params = {
            "page": 1,
            "limit": self._settings.easybroker_page_limit,
            "search[updated_after]": self._updated_after_filter(
                days_back if days_back is not None else self._settings.easybroker_days_back
            ),
        }

        contacts: list[Contact] = []
        while True:
            data = self._request_contacts(params)
            raw_contacts = data.get("content", [])
            if not raw_contacts:
                break

            contacts.extend(self._normalize_contact(item) for item in raw_contacts)
            pagination = data.get("pagination", {})
            if not pagination.get("next_page"):
                break
            params["page"] = int(params["page"]) + 1

        logger.info("EasyBroker sync fetched %s contacts", len(contacts))
        return contacts

    def _request_contacts(self, params: dict[str, object]) -> dict:
        headers = {
            "accept": "application/json",
            "X-Authorization": self._settings.easybroker_api_key,
        }
        last_error: Exception | None = None
        for attempt in range(1, self._settings.easybroker_max_retries + 1):
            try:
                response = self._session.get(
                    f"{self.base_url}/contacts",
                    headers=headers,
                    params=params,
                    timeout=self._settings.easybroker_timeout_seconds,
                )
                if 400 <= response.status_code < 500 and response.status_code not in {408, 429}:
                    raise EasyBrokerAPIError(
                        f"EasyBroker request failed with status {response.status_code}."
                    )
                response.raise_for_status()
                return response.json()
            except EasyBrokerAPIError:
                raise
            except requests.HTTPError as exc:
                last_error = exc
            except requests.RequestException as exc:
                last_error = exc

            if attempt < self._settings.easybroker_max_retries:
                backoff_seconds = 2 ** (attempt - 1)
                logger.warning(
                    "Retrying EasyBroker request after transient failure on page=%s",
                    params.get("page"),
                )
                self._sleep(backoff_seconds)

        raise EasyBrokerAPIError("EasyBroker request failed after retries.") from last_error

    def _updated_after_filter(self, days_back: int) -> str:
        now_mx = datetime.now(self._settings.timezone)
        target_day = now_mx - timedelta(days=days_back)
        start_of_day = target_day.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_of_day.isoformat()

    def _normalize_contact(self, raw: dict) -> Contact:
        return Contact(
            external_id=str(raw.get("id", "")).strip(),
            name=raw.get("name") or None,
            email=raw.get("email") or None,
            phone=raw.get("phone") or None,
            mobile_phone=raw.get("mobile_phone") or None,
            company=raw.get("company") or None,
            source=raw.get("source") or "EasyBroker",
            stage=raw.get("stage") or None,
            status=raw.get("status") or None,
            created_at=raw.get("created_at") or None,
            updated_at=raw.get("updated_at") or None,
        )
