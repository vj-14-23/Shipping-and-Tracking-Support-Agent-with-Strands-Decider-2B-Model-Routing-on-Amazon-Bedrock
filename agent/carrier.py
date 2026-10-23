"""Carrier API abstraction layer.

Provides a pluggable `CarrierClient` interface so the agent layer is decoupled from any specific
shipping carrier. Three built-in providers are supported (EasyPost, ShipEngine, AfterShip); new
providers can be added via `register_carrier()` without touching existing code (Requirement 5.5).

Usage:
    from agent.carrier import carrier_from_env
    client = carrier_from_env()          # reads CARRIER_PROVIDER and CARRIER_API_KEY from env
    shipment = client.get_shipment("9400111899225840025422")
"""

from __future__ import annotations

import logging
import os
import warnings
import boto3
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import requests

from agent.models import Address, AddressChangeResult, Shipment, TrackingEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class CarrierConfigError(RuntimeError):
    """Raised when the carrier cannot be configured from environment variables.

    The error message will NEVER include the value of CARRIER_API_KEY (Requirement 5.6).
    """


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class CarrierClient(ABC):
    """Abstract interface for shipping-carrier integrations.

    Concrete subclasses handle provider-specific HTTP calls.  The agent and tools layers interact
    only with this interface, so the underlying provider can be switched without code changes.
    """

    @abstractmethod
    def get_shipment(self, identifier: str) -> Shipment | None:
        """Return a :class:`Shipment` for *identifier* (tracking number or order ID).

        Returns ``None`` if the carrier API cannot find a shipment for the given identifier.
        Raises :exc:`CarrierAPIError` on network or server errors.

        Args:
            identifier: A tracking number (6â€“40 alphanumeric chars) or order ID (1â€“20 chars).

        Returns:
            A :class:`Shipment` dataclass instance, or ``None`` if not found.
        """

    @abstractmethod
    def change_address(self, tracking_no: str, new_address: Address) -> AddressChangeResult:
        """Request an address redirect for an in-transit shipment.

        Args:
            tracking_no: The carrier tracking number for the shipment to redirect.
            new_address: The new :class:`Address` to deliver to.  Must satisfy
                ``Address.is_complete()`` before this is called.

        Returns:
            An :class:`AddressChangeResult` describing whether the change was accepted.
        """


# ---------------------------------------------------------------------------
# Carrier API error and key-redaction helper
# ---------------------------------------------------------------------------


class CarrierAPIError(RuntimeError):
    """Raised by :class:`CarrierClient` implementations for network or server errors.

    Never include the CARRIER_API_KEY value in the message (Requirement 5.6).
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        # Defensive: ensure the API key is not accidentally included
        _redact_key(message)
        super().__init__(message)
        self.status_code = status_code


def _redact_key(text: str) -> str:
    """Return *text* with the CARRIER_API_KEY value replaced by ``[REDACTED]``.

    Used as a last-resort guard in ``CarrierAPIError`` and concrete client implementations.
    The function is intentionally tolerant: if no key is set it returns *text* unchanged.
    """
    key = os.environ.get("CARRIER_API_KEY", "")
    if key and key in text:
        return text.replace(key, "[REDACTED]")
    return text


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_TIMEOUT = 10  # seconds (Requirement 4.7)


def _parse_datetime(value: Any) -> datetime | None:
    """Best-effort parse of a datetime string; return ``None`` on failure."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _parse_events(raw_events: list[Any]) -> list[TrackingEvent]:
    """Convert a list of raw event dicts to :class:`TrackingEvent` objects, best-effort."""
    events: list[TrackingEvent] = []
    for ev in raw_events or []:
        if not isinstance(ev, dict):
            continue
        # Try common field names across providers.
        description = (
            ev.get("message")
            or ev.get("description")
            or ev.get("status_detail")
            or ev.get("status")
            or "Unknown event"
        )
        location = (
            ev.get("tracking_location", {}).get("city")
            or ev.get("location")
            or ev.get("city_locality")
            or "Unknown location"
        )
        ts = _parse_datetime(
            ev.get("datetime") or ev.get("occurred_at") or ev.get("created_at")
        )
        if ts is None:
            ts = datetime.now(tz=timezone.utc)
        events.append(TrackingEvent(description=str(description), location=str(location), timestamp=ts))
    return events


# ---------------------------------------------------------------------------
# Concrete implementations
# ---------------------------------------------------------------------------


class EasyPostClient(CarrierClient):
    """EasyPost carrier integration.

    Docs: https://www.easypost.com/docs/api
    """

    _BASE_URL = "https://api.easypost.com/v2"

    def __init__(self, api_key: str) -> None:
        # Store only a reference; never re-expose the value in logs or exceptions.
        self._api_key = api_key

    def get_shipment(self, identifier: str) -> Shipment | None:
        """GET /trackers?tracking_code={identifier} â€” returns the first matching tracker."""
        url = f"{self._BASE_URL}/trackers"
        headers = {"Authorization": f"EasyPost {self._api_key}"}
        try:
            resp = requests.get(
                url,
                params={"tracking_code": identifier},
                headers=headers,
                timeout=_TIMEOUT,
            )
        except requests.Timeout as exc:
            msg = _redact_key(f"EasyPost request timed out for identifier {identifier}: {exc}")
            logger.error(msg)
            raise CarrierAPIError(msg) from exc
        except requests.ConnectionError as exc:
            msg = _redact_key(f"EasyPost connection error for identifier {identifier}: {exc}")
            logger.error(msg)
            raise CarrierAPIError(msg) from exc

        if resp.status_code == 404:
            return None

        if not resp.ok:
            msg = _redact_key(
                f"EasyPost API returned HTTP {resp.status_code} for identifier {identifier}"
            )
            logger.error(msg)
            raise CarrierAPIError(msg, status_code=resp.status_code)

        data = resp.json()
        trackers: list[dict] = data.get("trackers", [])
        if not trackers:
            return None

        tracker = trackers[0]
        return Shipment(
            tracking_number=tracker.get("tracking_code") or identifier,
            carrier=tracker.get("carrier") or "EasyPost",
            status=tracker.get("status") or "unknown",
            estimated_delivery=_parse_datetime(tracker.get("est_delivery_date")),
            events=_parse_events(tracker.get("tracking_details", [])),
            raw=tracker,
        )

    def change_address(self, tracking_no: str, new_address: Address) -> AddressChangeResult:
        """EasyPost does not support in-flight address changes via its public API."""
        return AddressChangeResult(
            success=False,
            updated_address=None,
            revised_eta=None,
            error_reason="EasyPost does not support in-flight address changes via API",
        )


class ShipEngineClient(CarrierClient):
    """ShipEngine carrier integration.

    Docs: https://www.shipengine.com/docs/
    """

    _BASE_URL = "https://api.shipengine.com/v1"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def get_shipment(self, identifier: str) -> Shipment | None:
        """POST /tracking/start to begin/retrieve tracking for the given number."""
        url = f"{self._BASE_URL}/tracking/start"
        headers = {"API-Key": self._api_key, "Content-Type": "application/json"}
        payload = {"carrier_code": "stamps_com", "tracking_number": identifier}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=_TIMEOUT)
        except requests.Timeout as exc:
            msg = _redact_key(f"ShipEngine request timed out for identifier {identifier}: {exc}")
            logger.error(msg)
            raise CarrierAPIError(msg) from exc
        except requests.ConnectionError as exc:
            msg = _redact_key(f"ShipEngine connection error for identifier {identifier}: {exc}")
            logger.error(msg)
            raise CarrierAPIError(msg) from exc

        if resp.status_code == 404:
            return None

        if not resp.ok:
            msg = _redact_key(
                f"ShipEngine API returned HTTP {resp.status_code} for identifier {identifier}"
            )
            logger.error(msg)
            raise CarrierAPIError(msg, status_code=resp.status_code)

        data = resp.json()
        return Shipment(
            tracking_number=data.get("tracking_number") or identifier,
            carrier=data.get("carrier_code") or "ShipEngine",
            status=data.get("status_code") or data.get("status") or "unknown",
            estimated_delivery=_parse_datetime(data.get("estimated_delivery_date")),
            events=_parse_events(data.get("events", [])),
            raw=data,
        )

    def change_address(self, tracking_no: str, new_address: Address) -> AddressChangeResult:
        """ShipEngine address change is not supported in this integration."""
        return AddressChangeResult(
            success=False,
            updated_address=None,
            revised_eta=None,
            error_reason="ShipEngine address change not supported in this integration",
        )


class AfterShipClient(CarrierClient):
    """AfterShip carrier integration.

    Docs: https://www.aftership.com/docs/aftership/quickstart/api-quick-start
    """

    _BASE_URL = "https://api.aftership.com/v4"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def get_shipment(self, identifier: str) -> Shipment | None:
        """GET /trackings/{identifier} â€” returns tracking details."""
        url = f"{self._BASE_URL}/trackings/{identifier}"
        headers = {"aftership-api-key": self._api_key}
        try:
            resp = requests.get(url, headers=headers, timeout=_TIMEOUT)
        except requests.Timeout as exc:
            msg = _redact_key(f"AfterShip request timed out for identifier {identifier}: {exc}")
            logger.error(msg)
            raise CarrierAPIError(msg) from exc
        except requests.ConnectionError as exc:
            msg = _redact_key(f"AfterShip connection error for identifier {identifier}: {exc}")
            logger.error(msg)
            raise CarrierAPIError(msg) from exc

        if resp.status_code == 404:
            return None

        if not resp.ok:
            msg = _redact_key(
                f"AfterShip API returned HTTP {resp.status_code} for identifier {identifier}"
            )
            logger.error(msg)
            raise CarrierAPIError(msg, status_code=resp.status_code)

        body = resp.json()
        tracking: dict = body.get("data", {}).get("tracking", {})
        if not tracking:
            return None

        # AfterShip nests checkpoints under "checkpoints"
        checkpoints = tracking.get("checkpoints", [])
        events = _parse_events(checkpoints)

        return Shipment(
            tracking_number=tracking.get("tracking_number") or identifier,
            carrier=tracking.get("slug") or "AfterShip",
            status=tracking.get("tag") or tracking.get("subtag") or "unknown",
            estimated_delivery=_parse_datetime(
                tracking.get("expected_delivery") or tracking.get("estimated_delivery_date")
            ),
            events=events,
            raw=tracking,
        )

    def change_address(self, tracking_no: str, new_address: Address) -> AddressChangeResult:
        """AfterShip address change is not supported in this integration."""
        return AddressChangeResult(
            success=False,
            updated_address=None,
            revised_eta=None,
            error_reason="AfterShip address change not supported in this integration",
        )


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

# Maps lower-cased provider name â†’ CarrierClient subclass.
# Only the three built-in providers are pre-registered; call register_carrier() to add more.
_REGISTRY: dict[str, type[CarrierClient]] = {
    "easypost": EasyPostClient,
    "shipengine": ShipEngineClient,
    "aftership": AfterShipClient,
}


def register_carrier(name: str, cls: type[CarrierClient]) -> None:
    """Register a new carrier provider in the global registry.

    Allows adding providers without changing any existing carrier code (Requirement 5.5).

    Args:
        name: A unique, case-insensitive provider name (e.g. ``"fedex"``).
        cls:  A concrete :class:`CarrierClient` subclass.  Must accept ``api_key`` as its
              first positional argument.

    Example::

        from agent.carrier import register_carrier, CarrierClient

        class FedExClient(CarrierClient):
            def __init__(self, api_key: str) -> None: ...
            def get_shipment(self, identifier): ...
            def change_address(self, tracking_no, new_address): ...

        register_carrier("fedex", FedExClient)
    """
    _REGISTRY[name.lower()] = cls


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_DEFAULT_PROVIDER = "easypost"


def _carrier_api_key_from_env() -> str:
    """Read a local carrier key or retrieve it from AWS Secrets Manager."""
    api_key = os.environ.get("CARRIER_API_KEY", "").strip()
    if api_key:
        return api_key

    secret_arn = os.environ.get("CARRIER_API_KEY_SECRET_ARN", "").strip()
    if not secret_arn:
        raise CarrierConfigError(
            "Carrier API key is not configured. Set CARRIER_API_KEY or "
            "CARRIER_API_KEY_SECRET_ARN."
        )

    try:
        import boto3
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
        response = boto3.client("secretsmanager", region_name=region).get_secret_value(
            SecretId=secret_arn
        )
        api_key = response.get("SecretString", "").strip()
    except Exception as exc:
        # Do not include SDK exception details; they may contain sensitive information.
        raise CarrierConfigError(
            "Unable to retrieve the carrier API key from AWS Secrets Manager. "
            "Check the runtime IAM permissions and secret configuration."
        ) from None

    if not api_key:
        raise CarrierConfigError(
            "The configured carrier secret has no usable SecretString value."
        )
    return api_key

def carrier_from_env() -> CarrierClient:
    """Build and return a :class:`CarrierClient` from environment variables.

    Environment variables read:
        * ``CARRIER_PROVIDER`` â€” one of ``easypost``, ``shipengine``, ``aftership``, or any
          name previously passed to :func:`register_carrier`.  "not set" means the variable
          is absent *or* set to an empty string (Requirement 5.1).  Defaults to ``easypost``
          with a warning (Requirements 5.2, 5.3).
        * ``CARRIER_API_KEY`` â€” the API key for the selected carrier.  If absent or empty,
          a :exc:`CarrierConfigError` is raised immediately; the key value is **never**
          included in the error message (Requirements 5.4, 5.6).

    Returns:
        A configured :class:`CarrierClient` instance for the selected provider.

    Raises:
        :exc:`CarrierConfigError`: If ``CARRIER_API_KEY`` is absent or empty (Requirement 5.4).
    """
    # --- Read CARRIER_PROVIDER (Requirement 5.1 / 5.3) ---
    raw_provider = os.environ.get("CARRIER_PROVIDER", "").strip()
    if not raw_provider:
        # Variable absent or empty â†’ use EasyPost default and emit a warning (Requirement 5.3)
        warnings.warn(
            "CARRIER_PROVIDER is not set; using the default carrier provider (easypost). "
            "Set CARRIER_PROVIDER to 'easypost', 'shipengine', or 'aftership' to suppress this warning.",
            stacklevel=2,
        )
        provider_name = _DEFAULT_PROVIDER
    else:
        provider_name = raw_provider.lower()

    # --- Read CARRIER_API_KEY (Requirements 5.4, 5.6) ---
    api_key = _carrier_api_key_from_env()

    # --- Resolve provider class ---
    provider_cls = _REGISTRY.get(provider_name)
    if provider_cls is None:
        # Unrecognised provider: fall back to EasyPost and warn (mirrors Requirement 5.3 spirit)
        warnings.warn(
            f"Unknown CARRIER_PROVIDER '{provider_name}'; falling back to the default provider (easypost). "
            "Use register_carrier() to add support for this provider.",
            stacklevel=2,
        )
        provider_cls = _REGISTRY[_DEFAULT_PROVIDER]

    return provider_cls(api_key)

