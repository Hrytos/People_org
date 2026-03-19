"""
HubSpot integration client.

Provides contact property discovery and batch upsert support with
rate limiting and retry/backoff for HubSpot transient responses.
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional

import httpx

from ..core.config import (
    HUBSPOT_BASE_URL,
    HUBSPOT_MAX_RETRIES,
    HUBSPOT_RATE_LIMIT_PER_MINUTE,
    HUBSPOT_REQUEST_TIMEOUT,
    HUBSPOT_SERVICE_KEY,
)
from ..core.logging import setup_logger
from ..fullenrich.rate_limit import RateLimiter

logger = setup_logger(__name__)


class HubSpotClient:
    """Client for HubSpot CRM Contacts APIs."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = HUBSPOT_BASE_URL,
        timeout: int = HUBSPOT_REQUEST_TIMEOUT,
        rate_limit_per_minute: int = HUBSPOT_RATE_LIMIT_PER_MINUTE,
        max_retries: int = HUBSPOT_MAX_RETRIES,
    ):
        token = api_key or HUBSPOT_SERVICE_KEY
        if not token:
            raise ValueError("HUBSPOT_SERVICE_KEY is required for HubSpot sync")

        self.max_retries = max(1, max_retries)
        self._rate_limiter = RateLimiter(rate_limit_per_minute)
        self.client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(timeout=float(timeout)),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            follow_redirects=True,
        )

    def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        transient_statuses = {423, 429, 500, 502, 503, 504}

        for attempt in range(1, self.max_retries + 1):
            self._rate_limiter.acquire()
            response = self.client.request(method, endpoint, params=params, json=json)

            if response.status_code in transient_statuses and attempt < self.max_retries:
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    sleep_seconds = int(retry_after)
                else:
                    sleep_seconds = min(30.0, (2 ** (attempt - 1)) + random.uniform(0.2, 1.0))

                logger.warning(
                    "HubSpot transient status=%s endpoint=%s attempt=%s/%s, backing off %.2fs",
                    response.status_code,
                    endpoint,
                    attempt,
                    self.max_retries,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)
                continue

            if response.is_error:
                detail = ""
                try:
                    if response.content:
                        detail = response.text[:1000]
                except Exception:
                    detail = ""
                raise httpx.HTTPStatusError(
                    f"HubSpot API error {response.status_code} at {endpoint}: {detail}",
                    request=response.request,
                    response=response,
                )
            return response

        response.raise_for_status()
        return response

    def get_contact_properties(self) -> List[Dict[str, Any]]:
        """Fetch all contact properties from HubSpot."""
        response = self._request_with_retry("GET", "/crm/v3/properties/0-1")
        payload = response.json() if response.content else {}
        return payload.get("results", [])

    def validate_unique_contact_property(self, internal_name: str) -> bool:
        """
        Check if a contact property exists and is marked as unique.
        """
        properties = self.get_contact_properties()
        for prop in properties:
            if prop.get("name") == internal_name:
                return bool(prop.get("hasUniqueValue"))
        return False

    def batch_upsert_contacts(self, inputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert contacts using HubSpot batch upsert API."""
        if not inputs:
            return {"results": []}

        response = self._request_with_retry(
            "POST",
            "/crm/v3/objects/contacts/batch/upsert",
            json={"inputs": inputs},
        )
        return response.json() if response.content else {"results": []}

    def close(self):
        """Close underlying HTTP client."""
        self.client.close()

    def __enter__(self) -> "HubSpotClient":
        return self

    def __exit__(self, *args):
        self.close()
