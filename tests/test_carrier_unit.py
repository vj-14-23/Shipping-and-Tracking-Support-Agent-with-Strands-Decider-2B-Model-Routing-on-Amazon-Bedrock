"""Unit tests for carrier abstraction: carrier_from_env, registry, key redaction.

Requirements: 5.1, 5.3, 5.4, 5.6
"""
from __future__ import annotations

import warnings

import pytest

from agent.carrier import (
    CarrierClient,
    CarrierConfigError,
    EasyPostClient,
    ShipEngineClient,
    AfterShipClient,
    carrier_from_env,
    register_carrier,
    _REGISTRY,
    _redact_key,
)
from agent.models import AddressChangeResult


# ---------------------------------------------------------------------------
# Requirement 5.4 — missing / empty CARRIER_API_KEY raises CarrierConfigError
# ---------------------------------------------------------------------------

def test_carrier_from_env_missing_key_raises(monkeypatch):
    """Missing CARRIER_API_KEY must raise CarrierConfigError."""
    monkeypatch.delenv("CARRIER_API_KEY", raising=False)
    monkeypatch.setenv("CARRIER_PROVIDER", "easypost")
    with pytest.raises(CarrierConfigError) as exc_info:
        carrier_from_env()
    # Error message must mention the variable name so users know what to fix
    assert "CARRIER_API_KEY" in str(exc_info.value)


def test_carrier_from_env_empty_key_raises(monkeypatch):
    """Empty string for CARRIER_API_KEY must also raise CarrierConfigError."""
    monkeypatch.setenv("CARRIER_API_KEY", "")
    monkeypatch.setenv("CARRIER_PROVIDER", "easypost")
    with pytest.raises(CarrierConfigError):
        carrier_from_env()


# ---------------------------------------------------------------------------
# Requirement 5.3 — missing / empty CARRIER_PROVIDER defaults to EasyPost + warning
# ---------------------------------------------------------------------------

def test_carrier_from_env_missing_provider_uses_default(monkeypatch):
    """Absent CARRIER_PROVIDER should fall back to EasyPost and emit a warning."""
    monkeypatch.delenv("CARRIER_PROVIDER", raising=False)
    monkeypatch.setenv("CARRIER_API_KEY", "test-key-abc123")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client = carrier_from_env()
    assert isinstance(client, EasyPostClient)
    assert any("CARRIER_PROVIDER" in str(w.message) for w in caught)


def test_carrier_from_env_empty_provider_uses_default(monkeypatch):
    """Empty string CARRIER_PROVIDER should also default to EasyPost with a warning."""
    monkeypatch.setenv("CARRIER_PROVIDER", "")
    monkeypatch.setenv("CARRIER_API_KEY", "test-key-abc123")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client = carrier_from_env()
    assert isinstance(client, EasyPostClient)
    assert any("CARRIER_PROVIDER" in str(w.message) for w in caught)


# ---------------------------------------------------------------------------
# Requirement 5.3 — unrecognised CARRIER_PROVIDER falls back to EasyPost
# ---------------------------------------------------------------------------

def test_carrier_from_env_unknown_provider_falls_back(monkeypatch):
    """An unknown provider name must fall back to EasyPost and warn the caller."""
    monkeypatch.setenv("CARRIER_PROVIDER", "nonexistent_carrier_xyz")
    monkeypatch.setenv("CARRIER_API_KEY", "test-key-abc123")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client = carrier_from_env()
    assert isinstance(client, EasyPostClient)
    assert any("nonexistent_carrier_xyz" in str(w.message) for w in caught)


# ---------------------------------------------------------------------------
# Requirement 5.2 — valid providers resolve to correct client class
# ---------------------------------------------------------------------------

def test_carrier_from_env_easypost(monkeypatch):
    monkeypatch.setenv("CARRIER_PROVIDER", "easypost")
    monkeypatch.setenv("CARRIER_API_KEY", "test-key-ep")
    client = carrier_from_env()
    assert isinstance(client, EasyPostClient)


def test_carrier_from_env_shipengine(monkeypatch):
    monkeypatch.setenv("CARRIER_PROVIDER", "shipengine")
    monkeypatch.setenv("CARRIER_API_KEY", "test-key-se")
    client = carrier_from_env()
    assert isinstance(client, ShipEngineClient)


def test_carrier_from_env_aftership(monkeypatch):
    monkeypatch.setenv("CARRIER_PROVIDER", "aftership")
    monkeypatch.setenv("CARRIER_API_KEY", "test-key-as")
    client = carrier_from_env()
    assert isinstance(client, AfterShipClient)


# ---------------------------------------------------------------------------
# Requirement 5.6 — CARRIER_API_KEY value never appears in error messages
# ---------------------------------------------------------------------------

def test_api_key_absent_error_message_has_no_key_value(monkeypatch):
    """The CarrierConfigError for a missing key must not contain a raw key value."""
    monkeypatch.delenv("CARRIER_API_KEY", raising=False)
    monkeypatch.setenv("CARRIER_PROVIDER", "easypost")
    with pytest.raises(CarrierConfigError) as exc_info:
        carrier_from_env()
    # No key value is present (key is absent, so there is nothing to leak here).
    # The message should not accidentally echo any secret-sounding text.
    assert "secret" not in str(exc_info.value).lower()


def test_redact_key_replaces_key_in_text(monkeypatch):
    """_redact_key must replace the exact key value with [REDACTED]."""
    monkeypatch.setenv("CARRIER_API_KEY", "supersecretkey999")
    text = "Error connecting to API with key supersecretkey999 in header"
    redacted = _redact_key(text)
    assert "supersecretkey999" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_key_no_env_key_is_noop(monkeypatch):
    """When CARRIER_API_KEY is unset, _redact_key should return text unchanged."""
    monkeypatch.delenv("CARRIER_API_KEY", raising=False)
    text = "Some innocent log message"
    assert _redact_key(text) == text


def test_redact_key_multiple_occurrences(monkeypatch):
    """_redact_key must replace every occurrence of the key in the text."""
    monkeypatch.setenv("CARRIER_API_KEY", "mykey42")
    text = "first mykey42 then mykey42 again"
    redacted = _redact_key(text)
    assert "mykey42" not in redacted
    assert redacted.count("[REDACTED]") == 2


# ---------------------------------------------------------------------------
# Requirement 5.5 — register_carrier adds to registry without breaking existing entries
# ---------------------------------------------------------------------------

def test_register_carrier_adds_new_provider():
    """register_carrier must insert the new class and leave existing entries unchanged."""

    class DummyCarrier(CarrierClient):
        def __init__(self, api_key: str) -> None:
            self._api_key = api_key

        def get_shipment(self, identifier: str):
            return None

        def change_address(self, tracking_no: str, new_address):
            return AddressChangeResult(
                success=False,
                updated_address=None,
                revised_eta=None,
                error_reason="test stub",
            )

    # Use a unique name to avoid polluting other tests
    register_carrier("dummy_test_carrier_unique", DummyCarrier)

    assert "dummy_test_carrier_unique" in _REGISTRY
    assert _REGISTRY["dummy_test_carrier_unique"] is DummyCarrier
    # Built-in entries must be untouched
    assert _REGISTRY["easypost"] is EasyPostClient
    assert _REGISTRY["shipengine"] is ShipEngineClient
    assert _REGISTRY["aftership"] is AfterShipClient


def test_register_carrier_name_is_lowercased():
    """register_carrier key must be stored in lower-case form."""

    class AnotherDummy(CarrierClient):
        def __init__(self, api_key: str) -> None:
            self._api_key = api_key

        def get_shipment(self, identifier: str):
            return None

        def change_address(self, tracking_no: str, new_address):
            return AddressChangeResult(
                success=False, updated_address=None, revised_eta=None, error_reason="stub"
            )

    register_carrier("MixedCaseCarrier", AnotherDummy)
    assert "mixedcasecarrier" in _REGISTRY
    assert _REGISTRY["mixedcasecarrier"] is AnotherDummy


def test_registered_custom_provider_is_used(monkeypatch):
    """A provider added via register_carrier must be selected by carrier_from_env."""

    class CustomCarrier(CarrierClient):
        def __init__(self, api_key: str) -> None:
            self._api_key = api_key

        def get_shipment(self, identifier: str):
            return None

        def change_address(self, tracking_no: str, new_address):
            return AddressChangeResult(
                success=False, updated_address=None, revised_eta=None, error_reason="stub"
            )

    register_carrier("customtest", CustomCarrier)
    monkeypatch.setenv("CARRIER_PROVIDER", "customtest")
    monkeypatch.setenv("CARRIER_API_KEY", "test-key-custom")

    client = carrier_from_env()
    assert isinstance(client, CustomCarrier)
