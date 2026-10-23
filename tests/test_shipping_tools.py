"""Unit tests for agent/tools.py shipping tools.
Requirements: 3.4, 4.6, 6.1, 6.2
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from agent.models import Shipment, TrackingEvent, Address, AddressChangeResult
from agent.session import SessionStore
from agent.carrier import CarrierAPIError
from agent.tools import (
    set_current_session,
    lookup_shipment, list_cached_shipments,
    report_damage,
    initiate_carrier_investigation, request_replacement,
    initiate_refund, request_address_change,
    TOOLS, IRREVERSIBLE_TOOLS,
)


def _make_carrier(shipment=None, raise_exc=None):
    c = MagicMock()
    if raise_exc:
        c.get_shipment.side_effect = raise_exc
    else:
        c.get_shipment.return_value = shipment
    c.change_address.return_value = AddressChangeResult(
        success=True, updated_address=None, revised_eta=None, error_reason=None
    )
    return c


def _make_shipment(tracking="TRK001"):
    return Shipment(
        tracking_number=tracking, carrier="TestCo", status="in_transit",
        estimated_delivery=None,
        events=[TrackingEvent("Departed hub", "Chicago, IL",
                              datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc))],
        raw={},
    )


# lookup_shipment
def test_lookup_live_call():
    store, carrier = SessionStore(), _make_carrier(_make_shipment())
    set_current_session(store, carrier)
    r = lookup_shipment("TRK001")
    assert r["status"] == "in_transit" and r["source"] == "live"
    carrier.get_shipment.assert_called_once_with("TRK001")

def test_lookup_uses_cache_second_call():
    store, carrier = SessionStore(), _make_carrier(_make_shipment())
    set_current_session(store, carrier)
    lookup_shipment("TRK001")
    carrier.get_shipment.reset_mock()
    r = lookup_shipment("TRK001")
    assert r["source"] == "cache"
    carrier.get_shipment.assert_not_called()

def test_lookup_not_found():
    set_current_session(SessionStore(), _make_carrier(None))
    assert lookup_shipment("MISSING")["error"] == "tracking_not_found"

def test_lookup_carrier_unavailable():
    set_current_session(SessionStore(), _make_carrier(raise_exc=CarrierAPIError("timeout")))
    r = lookup_shipment("TRK001")
    assert r["error"] == "carrier_unavailable" and r["retry_after_minutes"] == 15

# list_cached_shipments
def test_list_empty():
    set_current_session(SessionStore(), _make_carrier())
    r = list_cached_shipments()
    assert r["identifiers"] == [] and r["count"] == 0

def test_list_after_lookup():
    store, carrier = SessionStore(), _make_carrier(_make_shipment("TRK42"))
    set_current_session(store, carrier)
    lookup_shipment("TRK42")
    assert "TRK42" in list_cached_shipments()["identifiers"]

# report_damage
def test_damage_valid():
    set_current_session(SessionStore(), _make_carrier())
    r = report_damage("ORDER1", "Screen cracked on arrival.")
    assert r["status"] == "damage_reported" and r["order_id"] == "ORDER1"

def test_damage_empty_description():
    set_current_session(SessionStore(), _make_carrier())
    assert report_damage("ORDER1", "")["error"] == "invalid_description"

def test_damage_too_long():
    set_current_session(SessionStore(), _make_carrier())
    assert report_damage("ORDER1", "x" * 1001)["error"] == "invalid_description"

def test_damage_exactly_1000_ok():
    set_current_session(SessionStore(), _make_carrier())
    assert report_damage("ORDER1", "y" * 1000)["status"] == "damage_reported"

def test_damage_empty_order_id():
    set_current_session(SessionStore(), _make_carrier())
    assert report_damage("", "damage")["error"] == "invalid_order_id"

def test_damage_order_id_too_long():
    set_current_session(SessionStore(), _make_carrier())
    assert report_damage("A" * 21, "damage")["error"] == "invalid_order_id"

# request_address_change
def test_address_change_incomplete():
    set_current_session(SessionStore(), _make_carrier())
    r = request_address_change("TRK001", "", "London", "SW1A1AA", "GB")
    assert r["error"] == "incomplete_address" and "street" in r["missing_fields"]

def test_address_change_success():
    carrier = _make_carrier()
    carrier.change_address.return_value = AddressChangeResult(True, None, None, None)
    set_current_session(SessionStore(), carrier)
    assert request_address_change("TRK001", "10 Baker St", "London", "SW1A1AA", "GB")["status"] == "address_changed"

def test_address_change_carrier_rejects():
    carrier = _make_carrier()
    carrier.change_address.return_value = AddressChangeResult(False, None, None, "Already out for delivery")
    set_current_session(SessionStore(), carrier)
    r = request_address_change("TRK001", "10 Baker St", "London", "SW1A1AA", "GB")
    assert r["status"] == "address_change_failed" and "Already out for delivery" in r["error_reason"]

# irreversible tools
def test_investigation_valid():
    set_current_session(SessionStore(), _make_carrier())
    assert initiate_carrier_investigation("TRK999")["status"] == "investigation_initiated"

def test_investigation_missing_tracking():
    set_current_session(SessionStore(), _make_carrier())
    assert initiate_carrier_investigation("")["error"] == "missing_tracking_number"

def test_replacement_valid():
    set_current_session(SessionStore(), _make_carrier())
    assert request_replacement("ORDER2")["status"] == "replacement_requested"

def test_refund_valid():
    set_current_session(SessionStore(), _make_carrier())
    r = initiate_refund("ORDER3", 49.99)
    assert r["status"] == "refund_initiated" and r["amount"] == 49.99

def test_refund_zero():
    set_current_session(SessionStore(), _make_carrier())
    assert initiate_refund("ORDER3", 0)["error"] == "invalid_amount"

def test_refund_negative():
    set_current_session(SessionStore(), _make_carrier())
    assert initiate_refund("ORDER3", -5)["error"] == "invalid_amount"

# exports
def test_tools_count():
    assert len(TOOLS) == 7

def test_irreversible_tools_set():
    assert IRREVERSIBLE_TOOLS == {"initiate_carrier_investigation", "request_replacement", "initiate_refund", "request_address_change"}
