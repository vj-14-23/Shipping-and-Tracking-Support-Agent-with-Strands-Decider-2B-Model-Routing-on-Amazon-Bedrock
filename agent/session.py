"""Session store and shipment cache for the shipping-tracking agent.

Manages per-session conversation state:
  - Up to 20 tracking identifiers, most-recent retained when cap exceeded (Req 6.1)
  - Shipment cache with 5-minute TTL per entry (Req 6.2)
  - 30-minute idle timeout before a session expires (Req 6.4)
  - No data carries over between sessions (Req 6.5)
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .models import Shipment

@dataclass
class CachedShipment:
    shipment: "Shipment"
    fetched_at: float  # time.time()

class SessionStore:
    MAX_IDS: int = 20
    CACHE_TTL: int = 300    # seconds (5 minutes), Requirement 6.2
    IDLE_TIMEOUT: int = 1800  # seconds (30 minutes), Requirement 6.4

    def __init__(self) -> None:
        self._identifiers: list[str] = []
        self._cache: dict[str, CachedShipment] = {}
        self._last_active: float = time.time()

    def touch(self) -> None:
        """Reset the idle timer."""
        self._last_active = time.time()

    def is_expired(self) -> bool:
        """True if the session has been idle for more than IDLE_TIMEOUT seconds."""
        return (time.time() - self._last_active) >= self.IDLE_TIMEOUT

    def add_identifier(self, identifier: str) -> None:
        """Record a tracking number / order ID; evict oldest if over MAX_IDS."""
        if identifier in self._identifiers:
            # Move to end (most recent)
            self._identifiers.remove(identifier)
        self._identifiers.append(identifier)
        while len(self._identifiers) > self.MAX_IDS:
            self._identifiers.pop(0)  # evict oldest
        self.touch()

    def identifiers(self) -> list[str]:
        """Return all retained identifiers (oldest first)."""
        return list(self._identifiers)

    def get_shipment(self, identifier: str) -> "Shipment | None":
        """Return cached Shipment if present and within TTL, else None."""
        entry = self._cache.get(identifier)
        if entry is None:
            return None
        if self.needs_refresh(identifier):
            return None
        return entry.shipment

    def put_shipment(self, identifier: str, shipment: "Shipment") -> None:
        """Store or refresh a Shipment in the cache."""
        self._cache[identifier] = CachedShipment(shipment=shipment, fetched_at=time.time())
        self.touch()

    def needs_refresh(self, identifier: str) -> bool:
        """True if the cached entry is absent or older than CACHE_TTL seconds."""
        entry = self._cache.get(identifier)
        if entry is None:
            return True
        return (time.time() - entry.fetched_at) >= self.CACHE_TTL

    def clear(self) -> None:
        """Discard all identifiers and cached shipment data."""
        self._identifiers.clear()
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._identifiers)
