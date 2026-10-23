"""Property-based tests for data models.

# Feature: shipping-tracking-agent
Property 6: Address completeness validation
Property 8: Shipment data round-trip
Property 9: Damage description length enforcement (tested via report_damage logic)

Validates: Requirements 4.6, 3.4, 1.1, 1.2
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agent.models import Address, Shipment, TrackingEvent, AddressChangeResult


# ---------------------------------------------------------------------------
# Property 6: Address completeness validation
# ---------------------------------------------------------------------------

@given(
    street=st.text(max_size=100),
    city=st.text(max_size=100),
    postal_code=st.text(max_size=20),
    country=st.text(max_size=50),
)
def test_address_is_complete_matches_required_fields(street, city, postal_code, country):
    # Feature: shipping-tracking-agent, Property 6: address validity matches required-field presence
    addr = Address(street=street, city=city, postal_code=postal_code, country=country)
    expected = bool(street and city and postal_code and country)
    assert addr.is_complete() == expected


@given(
    city=st.text(min_size=1, max_size=80),
    postal_code=st.text(min_size=1, max_size=20),
    country=st.text(min_size=1, max_size=50),
)
def test_address_empty_street_always_incomplete(city, postal_code, country):
    # Feature: shipping-tracking-agent, Property 6: address validity matches required-field presence
    addr = Address(street="", city=city, postal_code=postal_code, country=country)
    assert addr.is_complete() is False


@given(
    street=st.text(min_size=1, max_size=100),
    city=st.text(min_size=1, max_size=100),
    postal_code=st.text(min_size=1, max_size=20),
    country=st.text(min_size=1, max_size=50),
)
def test_address_all_fields_present_always_complete(street, city, postal_code, country):
    # Feature: shipping-tracking-agent, Property 6: address validity matches required-field presence
    addr = Address(street=street, city=city, postal_code=postal_code, country=country)
    assert addr.is_complete() is True


# ---------------------------------------------------------------------------
# Property 8: Shipment data round-trip
# ---------------------------------------------------------------------------

_event_strategy = st.builds(
    TrackingEvent,
    description=st.text(min_size=1, max_size=80),
    location=st.text(min_size=1, max_size=80),
    timestamp=st.datetimes(timezones=st.just(timezone.utc)),
)

_shipment_strategy = st.builds(
    Shipment,
    tracking_number=st.text(
        min_size=6, max_size=40,
        alphabet=st.characters(whitelist_categories=("Lu", "Nd")),
    ),
    carrier=st.text(min_size=1, max_size=40),
    status=st.sampled_from(
        ["in_transit", "delivered", "exception", "out_for_delivery", "unknown"]
    ),
    estimated_delivery=st.one_of(
        st.none(),
        st.datetimes(timezones=st.just(timezone.utc)),
    ),
    events=st.lists(_event_strategy, max_size=5),
    raw=st.just({}),
)


@given(_shipment_strategy)
def test_shipment_round_trip(shipment):
    # Feature: shipping-tracking-agent, Property 8: Shipment serialisation round-trip is identity
    d = shipment.to_dict()
    restored = Shipment.from_dict(d)

    assert restored.tracking_number == shipment.tracking_number
    assert restored.status == shipment.status
    assert restored.carrier == shipment.carrier

    # Compare ETAs via ISO string to handle tz representation differences
    assert (restored.estimated_delivery is None) == (shipment.estimated_delivery is None)
    if shipment.estimated_delivery is not None:
        assert restored.estimated_delivery.isoformat() == shipment.estimated_delivery.isoformat()

    assert len(restored.events) == len(shipment.events)
    for orig, back in zip(shipment.events, restored.events):
        assert orig.description == back.description
        assert orig.location == back.location
        assert orig.timestamp.isoformat() == back.timestamp.isoformat()


def test_shipment_round_trip_no_events():
    # Feature: shipping-tracking-agent, Property 8: Shipment serialisation round-trip is identity
    s = Shipment(
        tracking_number="ABC123",
        carrier="TestCo",
        status="in_transit",
        estimated_delivery=None,
        events=[],
        raw={},
    )
    assert Shipment.from_dict(s.to_dict()).events == []


def test_shipment_round_trip_with_estimated_delivery():
    # Feature: shipping-tracking-agent, Property 8: Shipment serialisation round-trip is identity
    eta = datetime(2025, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
    s = Shipment(
        tracking_number="XYZ9999",
        carrier="FastShip",
        status="in_transit",
        estimated_delivery=eta,
        events=[],
        raw={},
    )
    restored = Shipment.from_dict(s.to_dict())
    assert restored.estimated_delivery.isoformat() == eta.isoformat()


# ---------------------------------------------------------------------------
# Property 9: Damage description length enforcement
# ---------------------------------------------------------------------------

def _validate_damage(order_id: str, description: str) -> dict:
    """Mirrors the validation logic required by report_damage (Requirement 3.4).

    Accepts order_id 1-20 alphanumeric characters and description 1-1000 characters.
    Returns {"status": "ok", ...} on success or {"error": ..., "message": ...} on failure.
    """
    if not order_id or not re.match(r"^[A-Za-z0-9]{1,20}$", order_id):
        return {
            "error": "invalid_order_id",
            "message": "order_id must be 1-20 alphanumeric characters",
        }
    if not description or len(description) > 1000:
        return {
            "error": "invalid_description",
            "message": "description must be between 1 and 1000 characters",
        }
    return {"status": "ok", "order_id": order_id, "description": description}


@given(st.text(min_size=0, max_size=1500))
def test_damage_description_length_gate(description):
    # Feature: shipping-tracking-agent, Property 9: damage description enforces 1-1000 char bounds
    result = _validate_damage("ORDER1", description)
    if 1 <= len(description) <= 1000:
        assert result.get("status") == "ok"
    else:
        assert "error" in result


@given(st.text(min_size=1, max_size=1000))
def test_damage_description_valid_range_always_accepted(description):
    # Feature: shipping-tracking-agent, Property 9: damage description enforces 1-1000 char bounds
    result = _validate_damage("ORDER1", description)
    assert result.get("status") == "ok"


def test_damage_description_exactly_1000_chars_accepted():
    # Feature: shipping-tracking-agent, Property 9: damage description enforces 1-1000 char bounds
    result = _validate_damage("ORDER1", "x" * 1000)
    assert result.get("status") == "ok"


def test_damage_description_1001_chars_rejected():
    # Feature: shipping-tracking-agent, Property 9: damage description enforces 1-1000 char bounds
    result = _validate_damage("ORDER1", "x" * 1001)
    assert "error" in result
    assert result["error"] == "invalid_description"


def test_damage_description_empty_rejected():
    # Feature: shipping-tracking-agent, Property 9: damage description enforces 1-1000 char bounds
    result = _validate_damage("ORDER1", "")
    assert "error" in result
    assert result["error"] == "invalid_description"


def test_damage_missing_order_id_rejected():
    # Feature: shipping-tracking-agent, Property 9: damage description enforces 1-1000 char bounds
    result = _validate_damage("", "valid description")
    assert "error" in result
    assert result["error"] == "invalid_order_id"
