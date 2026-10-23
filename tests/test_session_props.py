"""Property-based tests for SessionStore.

# Feature: shipping-tracking-agent
Property 3: Session identifier cap and recency
Property 4: Shipment cache TTL boundary
Property 5: New session starts empty

Validates: Requirements 6.1, 6.2, 6.5
"""
from __future__ import annotations

import time
from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st

from agent.session import SessionStore
from agent.models import Shipment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_shipment(tracking_number: str = "TEST123") -> Shipment:
    return Shipment(
        tracking_number=tracking_number,
        carrier="TestCarrier",
        status="in_transit",
        estimated_delivery=None,
        events=[],
        raw={},
    )


# ---------------------------------------------------------------------------
# Property 3: Session identifier cap and recency
# ---------------------------------------------------------------------------

@given(
    identifiers=st.lists(
        st.text(min_size=1, max_size=30),
        min_size=1,
        max_size=50,
    )
)
def test_session_identifier_cap_and_recency(identifiers):
    # Feature: shipping-tracking-agent, Property 3: session cap preserves most-recent identifiers
    store = SessionStore()
    for ident in identifiers:
        store.add_identifier(ident)

    # Cap is never exceeded (Requirement 6.1)
    assert len(store) <= SessionStore.MAX_IDS

    # The retained set equals the last MAX_IDS *unique* identifiers added.
    # Build the expected set: walk identifiers, track last-seen index per unique value,
    # then keep the final MAX_IDS by last-seen order.
    last_seen: dict[str, int] = {}
    for i, ident in enumerate(identifiers):
        last_seen[ident] = i
    # Sort by last-seen position ascending, then take the tail MAX_IDS
    ordered_unique = sorted(last_seen.keys(), key=lambda k: last_seen[k])
    expected = set(ordered_unique[-SessionStore.MAX_IDS :])

    assert set(store.identifiers()) == expected


@given(
    identifiers=st.lists(
        st.text(
            min_size=1,
            max_size=10,
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        ),
        min_size=SessionStore.MAX_IDS + 1,
        max_size=50,
        unique=True,
    )
)
def test_session_never_exceeds_max_ids_unique(identifiers):
    # Feature: shipping-tracking-agent, Property 3: session cap preserves most-recent identifiers
    store = SessionStore()
    for ident in identifiers:
        store.add_identifier(ident)
    assert len(store) == SessionStore.MAX_IDS


# ---------------------------------------------------------------------------
# Property 4: Shipment cache TTL boundary
# ---------------------------------------------------------------------------

@given(st.integers(min_value=0, max_value=600))
def test_cache_ttl_boundary(age_seconds):
    # Feature: shipping-tracking-agent, Property 4: cache TTL boundary is exactly 300 seconds
    store = SessionStore()
    shipment = _make_shipment()
    fake_now = time.time()

    with patch("agent.session.time") as mock_time:
        # Cache entry stored at (fake_now - age_seconds)
        mock_time.time.return_value = fake_now - age_seconds
        store.put_shipment("T1", shipment)

        # Refresh check evaluated at fake_now
        mock_time.time.return_value = fake_now
        result = store.needs_refresh("T1")

    if age_seconds < SessionStore.CACHE_TTL:
        assert result is False, (
            f"age {age_seconds}s < TTL {SessionStore.CACHE_TTL}s should NOT need refresh"
        )
    else:
        assert result is True, (
            f"age {age_seconds}s >= TTL {SessionStore.CACHE_TTL}s SHOULD need refresh"
        )


@given(st.integers(min_value=1, max_value=SessionStore.CACHE_TTL - 1))
def test_cache_within_ttl_never_needs_refresh(age_seconds):
    # Feature: shipping-tracking-agent, Property 4: cache TTL boundary is exactly 300 seconds
    store = SessionStore()
    fake_now = time.time()

    with patch("agent.session.time") as mock_time:
        mock_time.time.return_value = fake_now - age_seconds
        store.put_shipment("T2", _make_shipment("T2"))

        mock_time.time.return_value = fake_now
        assert store.needs_refresh("T2") is False


@given(st.integers(min_value=SessionStore.CACHE_TTL, max_value=3600))
def test_cache_at_or_past_ttl_always_needs_refresh(age_seconds):
    # Feature: shipping-tracking-agent, Property 4: cache TTL boundary is exactly 300 seconds
    store = SessionStore()
    fake_now = time.time()

    with patch("agent.session.time") as mock_time:
        mock_time.time.return_value = fake_now - age_seconds
        store.put_shipment("T3", _make_shipment("T3"))

        mock_time.time.return_value = fake_now
        assert store.needs_refresh("T3") is True


# ---------------------------------------------------------------------------
# Property 5: New session starts empty
# ---------------------------------------------------------------------------

@given(
    ids_a=st.lists(
        st.text(min_size=1, max_size=20),
        min_size=1,
        max_size=5,
    )
)
def test_new_session_starts_empty(ids_a):
    # Feature: shipping-tracking-agent, Property 5: new session contains no data from any prior session
    store_a = SessionStore()
    for ident in ids_a:
        store_a.add_identifier(ident)
        store_a.put_shipment(ident, _make_shipment(ident))

    # Completely independent SessionStore starts empty (Requirement 6.5)
    store_b = SessionStore()
    assert len(store_b) == 0
    for ident in ids_a:
        assert store_b.get_shipment(ident) is None
    assert store_b.identifiers() == []


# ---------------------------------------------------------------------------
# Deterministic unit tests
# ---------------------------------------------------------------------------

def test_identifier_eviction_keeps_most_recent():
    """After adding 25 unique IDs, only the last 20 must be retained."""
    store = SessionStore()
    for i in range(25):
        store.add_identifier(f"ID{i:03d}")
    retained = store.identifiers()
    assert len(retained) == 20
    for i in range(5):
        assert f"ID{i:03d}" not in retained
    for i in range(5, 25):
        assert f"ID{i:03d}" in retained


def test_duplicate_identifier_moves_to_tail():
    """Re-adding an existing identifier should move it to the most-recent position."""
    store = SessionStore()
    for i in range(20):
        store.add_identifier(f"ID{i:03d}")
    # Re-add the oldest; it should now be at the tail (most recent)
    store.add_identifier("ID000")
    ids = store.identifiers()
    assert ids[-1] == "ID000"
    # Length unchanged
    assert len(ids) == 20


def test_unknown_identifier_needs_refresh():
    """needs_refresh must return True when the identifier has never been cached."""
    store = SessionStore()
    assert store.needs_refresh("NOSUCHKEY") is True


def test_session_is_expired_after_idle_timeout():
    """A session that has been idle for exactly IDLE_TIMEOUT seconds must be expired."""
    fake_now = time.time()
    with patch("agent.session.time") as mock_time:
        mock_time.time.return_value = fake_now
        store = SessionStore()
        mock_time.time.return_value = fake_now + SessionStore.IDLE_TIMEOUT
        assert store.is_expired() is True


def test_session_not_expired_before_timeout():
    """A session idle for just under IDLE_TIMEOUT seconds must not be expired."""
    fake_now = time.time()
    with patch("agent.session.time") as mock_time:
        mock_time.time.return_value = fake_now
        store = SessionStore()
        mock_time.time.return_value = fake_now + SessionStore.IDLE_TIMEOUT - 1
        assert store.is_expired() is False


def test_clear_removes_all_data():
    """clear() must empty both the identifier list and the shipment cache."""
    store = SessionStore()
    store.add_identifier("T1")
    store.put_shipment("T1", _make_shipment("T1"))
    store.clear()
    assert len(store) == 0
    assert store.get_shipment("T1") is None
    assert store.identifiers() == []


def test_get_shipment_returns_none_for_expired_entry():
    """get_shipment must return None when the cached entry has exceeded the TTL."""
    fake_now = time.time()
    store = SessionStore()
    with patch("agent.session.time") as mock_time:
        mock_time.time.return_value = fake_now - SessionStore.CACHE_TTL
        store.put_shipment("T4", _make_shipment("T4"))

        mock_time.time.return_value = fake_now
        assert store.get_shipment("T4") is None


def test_get_shipment_returns_shipment_within_ttl():
    """get_shipment must return the cached Shipment when it is still fresh."""
    fake_now = time.time()
    shipment = _make_shipment("T5")
    store = SessionStore()
    with patch("agent.session.time") as mock_time:
        mock_time.time.return_value = fake_now - (SessionStore.CACHE_TTL - 1)
        store.put_shipment("T5", shipment)

        mock_time.time.return_value = fake_now
        result = store.get_shipment("T5")
    assert result is shipment
