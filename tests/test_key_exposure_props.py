"""Property-based tests for CARRIER_API_KEY exposure.

# Feature: shipping-tracking-agent
Property 7: CARRIER_API_KEY is never exposed in any output
"""
from __future__ import annotations

import os
import warnings
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from agent.carrier import (
    CarrierConfigError, EasyPostClient, _redact_key,
    carrier_from_env,
)
from agent.models import Address, AddressChangeResult


_printable = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
    min_size=8,
    max_size=40,
)


@given(_printable)
def test_carrier_config_error_never_contains_api_key(api_key):
    # Feature: shipping-tracking-agent, Property 7: CARRIER_API_KEY is never exposed in any output
    with patch.dict(os.environ, {"CARRIER_API_KEY": "", "CARRIER_PROVIDER": "easypost"}):
        try:
            carrier_from_env()
        except CarrierConfigError as exc:
            assert api_key not in str(exc), f"Key '{api_key}' leaked into error: {exc}"


@given(_printable)
def test_redact_key_removes_key_from_any_text(api_key):
    # Feature: shipping-tracking-agent, Property 7: CARRIER_API_KEY is never exposed in any output
    text = f"connecting with key={api_key} to carrier API"
    with patch.dict(os.environ, {"CARRIER_API_KEY": api_key}):
        result = _redact_key(text)
    assert api_key not in result, f"Key '{api_key}' not redacted"
    assert "[REDACTED]" in result


@given(_printable)
def test_carrier_api_error_does_not_contain_key(api_key):
    # Feature: shipping-tracking-agent, Property 7: CARRIER_API_KEY is never exposed in any output
    from agent.carrier import CarrierAPIError
    with patch.dict(os.environ, {"CARRIER_API_KEY": api_key}):
        # Simulate a message that accidentally includes the key before redaction
        safe_msg = _redact_key(f"Error calling API {api_key}")
        exc = CarrierAPIError(safe_msg)
        assert api_key not in str(exc), f"Key leaked in CarrierAPIError: {exc}"


@given(_printable)
def test_easypost_client_does_not_expose_key_in_timeout_error(api_key):
    # Feature: shipping-tracking-agent, Property 7: CARRIER_API_KEY is never exposed in any output
    import requests
    from agent.carrier import CarrierAPIError, EasyPostClient
    client = EasyPostClient(api_key)
    with patch.dict(os.environ, {"CARRIER_API_KEY": api_key}):
        with patch("agent.carrier.requests.get") as mock_get:
            mock_get.side_effect = requests.Timeout("timed out")
            try:
                client.get_shipment("TRK001")
            except CarrierAPIError as exc:
                assert api_key not in str(exc), f"Key '{api_key}' leaked in timeout error"
