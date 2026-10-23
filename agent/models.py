"""Data models for the shipping-tracking agent.

Defines the core dataclasses used throughout the agent:
  - TrackingEvent  – a single carrier scan event
  - Shipment       – full shipment record from the Carrier_API
  - Address        – delivery address with completeness validation
  - AddressChangeResult – outcome of a carrier address-change request
  - RoutingDecision – log entry produced by ModelRouter per chat turn
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# TrackingEvent
# ---------------------------------------------------------------------------

@dataclass
class TrackingEvent:
    """A single carrier scan / tracking event."""

    description: str
    location: str
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "location": self.location,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TrackingEvent":
        ts = d["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        return cls(
            description=d["description"],
            location=d["location"],
            timestamp=ts,
        )


# ---------------------------------------------------------------------------
# Shipment
# ---------------------------------------------------------------------------

# Exception status strings that indicate a delivery problem.
_EXCEPTION_STATUSES = frozenset(
    {
        "exception",
        "delivery_exception",
        "failed_attempt",
        "return_to_sender",
        "damaged",
        "lost",
        "unknown",
        "error",
    }
)

# Number of days past the estimated delivery date that implies a lost package
# (Requirement 3.3).
LOST_PACKAGE_THRESHOLD_DAYS = 7


@dataclass
class Shipment:
    """Full shipment record as returned (and normalised) from the Carrier_API.

    The ``raw`` field stores the provider-specific payload; it is never sent to
    the customer or logged to external systems (Requirement 5.6).
    """

    tracking_number: str
    carrier: str
    status: str                          # e.g. "in_transit", "delivered", "exception"
    estimated_delivery: datetime | None
    events: list[TrackingEvent]
    raw: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def latest_event(self) -> TrackingEvent | None:
        """Return the most-recent tracking event, or ``None`` if there are none."""
        if not self.events:
            return None
        # Events may not be pre-sorted; pick the one with the greatest timestamp.
        return max(self.events, key=lambda e: e.timestamp)

    @property
    def is_exception(self) -> bool:
        """Return ``True`` when the shipment status signals a delivery problem."""
        return self.status.lower() in _EXCEPTION_STATUSES

    def days_since_estimated_delivery(self) -> int | None:
        """Return the number of whole days elapsed since the ETA.

        Returns ``None`` when no ETA is set.  A negative value means the ETA is
        still in the future.  Used to detect lost packages (> 7 days, Req 3.3).
        """
        if self.estimated_delivery is None:
            return None

        # Ensure both sides are timezone-aware for arithmetic; treat naïve
        # datetimes as UTC.
        eta = self.estimated_delivery
        if eta.tzinfo is None:
            eta = eta.replace(tzinfo=timezone.utc)

        now = datetime.now(tz=timezone.utc)
        delta = now - eta
        return delta.days

    # ------------------------------------------------------------------
    # Serialisation helpers (plain-dict round-trip, Requirement 1.1 / 1.2)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict suitable for JSON transport.

        The ``raw`` field is included so a round-trip is lossless, but callers
        that build customer-facing responses should omit it.
        """
        return {
            "tracking_number": self.tracking_number,
            "carrier": self.carrier,
            "status": self.status,
            "estimated_delivery": (
                self.estimated_delivery.isoformat()
                if self.estimated_delivery is not None
                else None
            ),
            "events": [e.to_dict() for e in self.events],
            "raw": self.raw,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Shipment":
        """Deserialise from a plain dict produced by :meth:`to_dict`."""
        ed = d.get("estimated_delivery")
        if isinstance(ed, str):
            ed = datetime.fromisoformat(ed)

        events = [
            TrackingEvent.from_dict(ev) if isinstance(ev, dict) else ev
            for ev in d.get("events", [])
        ]

        return cls(
            tracking_number=d["tracking_number"],
            carrier=d["carrier"],
            status=d["status"],
            estimated_delivery=ed,
            events=events,
            raw=d.get("raw", {}),
        )


# ---------------------------------------------------------------------------
# Address
# ---------------------------------------------------------------------------

@dataclass
class Address:
    """Delivery address for a shipment or an address-change request.

    Required fields are ``street``, ``city``, ``postal_code``, and ``country``.
    ``state`` and ``name`` are optional.
    """

    street: str
    city: str
    postal_code: str
    country: str
    state: str | None = None
    name: str | None = None

    def is_complete(self) -> bool:
        """Return ``True`` iff all four required fields are non-empty strings.

        Requirement 4.6: the agent must verify that street, city, postal_code,
        and country are all present before submitting an address change.
        """
        return bool(self.street and self.city and self.postal_code and self.country)

    def to_dict(self) -> dict[str, Any]:
        return {
            "street": self.street,
            "city": self.city,
            "postal_code": self.postal_code,
            "country": self.country,
            "state": self.state,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Address":
        return cls(
            street=d.get("street", ""),
            city=d.get("city", ""),
            postal_code=d.get("postal_code", ""),
            country=d.get("country", ""),
            state=d.get("state"),
            name=d.get("name"),
        )


# ---------------------------------------------------------------------------
# AddressChangeResult
# ---------------------------------------------------------------------------

@dataclass
class AddressChangeResult:
    """Outcome of a ``CarrierClient.change_address()`` call."""

    success: bool
    updated_address: Address | None
    revised_eta: datetime | None
    error_reason: str | None  # non-None when success is False

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "updated_address": (
                self.updated_address.to_dict()
                if self.updated_address is not None
                else None
            ),
            "revised_eta": (
                self.revised_eta.isoformat()
                if self.revised_eta is not None
                else None
            ),
            "error_reason": self.error_reason,
        }


# ---------------------------------------------------------------------------
# RoutingDecision
# ---------------------------------------------------------------------------

@dataclass
class RoutingDecision:
    """Log entry produced by the ModelRouter for each chat turn.

    Serialised into the ``decisions`` list of every :meth:`ShippingTrackingAgent.chat`
    response (Requirements 2.6, 7.1, 7.2).
    """

    query_category: str    # "simple" | "complex"
    confidence: float      # 0.0 – 1.0
    selected_model_id: str
    latency_ms: int        # non-negative integer, milliseconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_category": self.query_category,
            "confidence": self.confidence,
            "selected_model_id": self.selected_model_id,
            "latency_ms": self.latency_ms,
        }
