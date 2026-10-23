# Implementation Plan: Shipping Tracking Agent

## Overview

Implement the shipping-tracking-agent by building on top of the existing `decider_kit` patterns. The agent is written in Python and reuses `ModelRouter`, `InterventionHandler`, and the `Decider` client without modification. Tasks are ordered so each step produces runnable, testable code before the next step depends on it.

## Tasks

- [x] 1. Create data models and carrier abstraction layer
  - [x] 1.1 Define `TrackingEvent`, `Shipment`, `Address`, and `AddressChangeResult` dataclasses in `agent/models.py`
    - Implement `Shipment.latest_event`, `Shipment.is_exception`, and `Shipment.days_since_estimated_delivery()`
    - Implement `Address.is_complete()` — returns `True` iff all four required fields are non-empty
    - Add `Shipment` serialise/deserialise helpers (plain dict round-trip)
    - _Requirements: 1.1, 1.2, 1.3, 3.3, 4.6_

  - [x]* 1.2 Write property tests for data models
    - **Property 6: Address completeness validation** — generate `Address` instances with arbitrary strings (including empty); assert `is_complete()` matches required-field presence
    - **Property 8: Shipment data round-trip** — generate `Shipment` instances; serialise → deserialise; assert structural equality
    - **Property 9: Damage description length enforcement** — generate strings of length 0–1500; assert `report_damage` tool accepts 1–1000 chars and rejects 0 and > 1000
    - Tag each test: `# Feature: shipping-tracking-agent, Property N: ...`
    - _Requirements: 4.6, 3.4, 1.1, 1.2_

  - [x] 1.3 Implement `CarrierClient` abstract base class and provider registry in `agent/carrier.py`
    - Define `CarrierClient(ABC)` with abstract `get_shipment(identifier)` and `change_address(tracking_no, new_address)`
    - Implement `_REGISTRY` dict and `register_carrier(name, cls)` function
    - Implement `carrier_from_env()`: read `CARRIER_PROVIDER` (default `easypost`) and `CARRIER_API_KEY`; raise `CarrierConfigError` if key is absent or empty; emit warning if provider not set; never log key value
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 1.4 Implement stub carrier clients for EasyPost, ShipEngine, and AfterShip in `agent/carrier.py`
    - Each client wraps HTTP calls with a 10-second timeout; catch `Timeout` and `ConnectionError` and return structured error dicts
    - Map provider-specific response payloads to the `Shipment` dataclass
    - Redact `CARRIER_API_KEY` from all exceptions and log messages
    - _Requirements: 1.1, 1.5, 4.7, 5.2, 5.6_

  - [x]* 1.5 Write unit tests for carrier abstraction
    - Test `carrier_from_env()` with missing key raises `CarrierConfigError`
    - Test unrecognised `CARRIER_PROVIDER` falls back to EasyPost with warning
    - Test `CARRIER_API_KEY` value absent from error messages
    - _Requirements: 5.1, 5.3, 5.4, 5.6_

- [x] 2. Implement session store and shipment cache
  - [x] 2.1 Implement `SessionStore` in `agent/session.py`
    - Fields: `_identifiers` (ordered list, max 20), `_cache` (dict of `CachedShipment`), `_last_active` timestamp
    - `add_identifier(identifier)`: append; evict oldest when over 20
    - `get_shipment(identifier)` / `put_shipment(identifier, shipment)` / `needs_refresh(identifier)`: TTL = 300 seconds
    - `touch()`, `is_expired()` (30-minute idle timeout), `clear()`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x]* 2.2 Write property tests for `SessionStore`
    - **Property 3: Session identifier cap and recency** — generate lists of 1–50 identifiers; add all; assert `len <= 20` and retained set equals the last 20 added
    - **Property 4: Shipment cache TTL boundary** — generate age offsets 0–600 s; assert `needs_refresh()` is `False` for `offset < 300` and `True` for `offset >= 300`
    - **Property 5: New session starts empty** — generate pairs of distinct session IDs; assert second `SessionStore` contains no data from the first
    - Tag each test: `# Feature: shipping-tracking-agent, Property N: ...`
    - _Requirements: 6.1, 6.2, 6.5_

- [x] 3. Checkpoint — ensure data layer tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement Strands tools
  - [x] 4.1 Implement read-only carrier tools in `agent/tools.py`
    - `lookup_shipment(identifier)`: check session cache (via `SessionStore`); call `CarrierClient.get_shipment()` on cache miss or when `needs_refresh()` is `True`; add identifier to session; return formatted status string
    - `list_cached_shipments()`: return all tracking numbers held in the current session
    - Replace the existing order-support tool stubs; keep `@tool` decorators and one-line docstrings
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 6.1, 6.2, 6.3_

  - [x] 4.2 Implement damage-report tool in `agent/tools.py`
    - `report_damage(order_id, description)`: validate `order_id` (non-empty, 1–20 alphanumeric) and `description` (1–1000 chars); return structured error dict on validation failure; return success dict with both fields on success
    - _Requirements: 3.4, 3.5_

  - [x] 4.3 Implement irreversible action tools in `agent/tools.py`
    - `initiate_carrier_investigation(tracking_no)`: call `CarrierClient`; return investigation reference or error
    - `request_replacement(order_id)`: record replacement request; return confirmation or error
    - `initiate_refund(order_id, amount)`: validate amount > 0; call refund endpoint; return confirmation or error
    - `request_address_change(tracking_no, new_address_dict)`: validate `Address.is_complete()`; call `CarrierClient.change_address()` with 10-second timeout; return `AddressChangeResult` as dict
    - _Requirements: 3.2, 3.3, 3.6, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [x]* 4.4 Write unit tests for tools
    - Test `lookup_shipment` uses cache within TTL and re-queries after TTL expiry
    - Test `report_damage` rejects empty description and description > 1000 chars
    - Test `report_damage` rejects missing `order_id`
    - Test `request_address_change` rejects incomplete `Address`
    - _Requirements: 3.4, 4.6, 6.2_

- [x] 5. Implement `ShippingActionGuard` intervention handler
  - [x] 5.1 Implement `ShippingActionGuard` in `agent/decision.py`
    - Replace `OrderActionGuard` with `ShippingActionGuard`; set `GUARDED_TOOLS` to the four irreversible shipping tools
    - Rewrite `QUESTIONS` for the shipping domain (`args_grounded`, `explicit_request`, `premature`)
    - Add `before_invocation()` input guard (injection / out-of-scope check using `scope="shipping and order-tracking support"`)
    - Implement `before_tool_call()` with `Proceed / Guide / Confirm / Deny` logic mirroring the kit's `OrderActionGuard` thresholds
    - Collect log entries with keys: `pattern`, `tool`, `args`, `args_grounded`, `explicit_request`, `premature`, `decider_ms`, `verdict`
    - _Requirements: 3.1, 3.6, 4.1, 4.2, 4.5, 2.5_

  - [x]* 5.2 Write unit tests for `ShippingActionGuard`
    - Test that each guarded tool name appears in `GUARDED_TOOLS`
    - Test that log entries contain required keys for each verdict type (proceed, guide, confirm, deny)
    - Mock `Decider.ask` to simulate `DeciderError`; assert irreversible calls fall back to `Confirm`
    - _Requirements: 2.5, 3.6_

- [x] 6. Implement `ShippingTrackingAgent` (top-level agent class)
  - [x] 6.1 Implement `ShippingTrackingAgent` in `agent/agent.py`
    - Replace `HackathonAgent` with `ShippingTrackingAgent`; preserve `chat(message, session_id, images)` signature and return shape `{"reply", "decisions", "model_id", "latency_ms", "agent", "tier"}`
    - `__init__`: initialise `Decider`, `ModelRouter`, `CarrierClient` (via `carrier_from_env()`); catch `CarrierConfigError` and store error for graceful `chat()` response
    - Per-turn `chat()`: evict expired sessions (`_evict_expired()`); retrieve or create `SessionStore`; call `ModelRouter.route(message)`; build `strands.Agent` with routed `model_id`, carrier tools, and `ShippingActionGuard`; invoke agent; strip `<thinking>` blocks; merge router and guard decision logs; return response dict
    - Set `NAME` and `SYSTEM_PROMPT` appropriate for the shipping domain
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 6.4, 6.5, 7.1_

  - [x] 6.2 Add `RoutingDecision` serialisation to the `decisions` field
    - Map `ModelRouter` log entries to `RoutingDecision` shape: `query_category`, `confidence`, `selected_model_id`, `latency_ms`
    - Map `ShippingActionGuard` log entries to the same shape where applicable
    - Ensure `decisions` list length is between 0 and 50 inclusive per turn
    - _Requirements: 2.6, 7.1, 7.2_

  - [x]* 6.3 Write property tests for model routing and decisions
    - **Property 1: Model routing confidence fallback** — generate routing labels and confidence values in [0.0, 0.5); mock `Decider.ask`; assert `ModelRouter` always selects the `large` tier's `model_id`
    - **Property 2: Routing decision log completeness** — generate arbitrary messages; mock `Decider.ask` with varied outputs; assert every `decisions` entry has `0.0 <= confidence <= 1.0`, `latency_ms >= 0`, and non-empty `selected_model_id`
    - Tag each test: `# Feature: shipping-tracking-agent, Property N: ...`
    - _Requirements: 2.4, 2.6, 7.1, 7.2_

  - [x]* 6.4 Write property tests for CARRIER_API_KEY exposure
    - **Property 7: CARRIER_API_KEY never in output** — generate arbitrary printable strings as `CARRIER_API_KEY`; mock carrier and force error/log paths; assert key value does not appear as a substring in any dict value, log entry, or exception message
    - Tag: `# Feature: shipping-tracking-agent, Property 7: CARRIER_API_KEY is never exposed in any output`
    - _Requirements: 5.6_

- [x] 7. Checkpoint — ensure agent and routing tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Wire `HackathonAgent` alias and update entry points
  - [x] 8.1 Add `HackathonAgent` alias and update `agent/__init__.py`
    - Alias `HackathonAgent = ShippingTrackingAgent` so the demo UI, benchmark, and `deploy/app/agent/main.py` continue to import `HackathonAgent` unchanged
    - Export `NAME` from `agent/__init__.py`
    - Update `TOOLS` export in `agent/tools.py` to include all shipping tools
    - _Requirements: 1.6, 2.1_

  - [x] 8.2 Update system prompt and demo script
    - Replace the kit's `SYSTEM_PROMPT` with a shipping-domain prompt that instructs the agent on tracking, delivery exceptions, address changes, and confirmation behaviour for irreversible actions
    - Update `agent/demo_script.yaml` with shipping-domain conversation examples covering status lookup, exception handling, address change, and damage claim
    - _Requirements: 1.1, 3.2, 3.6, 4.5_

  - [ ]* 8.3 Write demo UI smoke tests
    - Test `GET /api/info` returns `agent`, `llm`, `decider`, `target` keys
    - Test `POST /api/chat {"message": "Track my package", "session_id": "test"}` returns `reply` and `decisions` keys
    - Test `POST /api/reset` clears the agent singleton
    - _Requirements: 7.3_

- [x] 9. Add pytest configuration and conftest
  - [x] 9.1 Create `pytest.ini` and `conftest.py` for Hypothesis
    - Add `[pytest] addopts = --hypothesis-seed=0` and `filterwarnings = ignore::DeprecationWarning` to `pytest.ini`
    - Register Hypothesis profiles `ci` (max_examples=200) and `dev` (max_examples=50) in `conftest.py`
    - _Requirements: (testing infrastructure)_

  - [ ]* 9.2 Write integration tests
    - Test carrier lookup returns a well-formed `Shipment` against a recorded VCR cassette or sandbox
    - Test `ModelRouter` makes a live Decider call and returns a valid `Route`
    - Test end-to-end `chat("Track my package A1002")` returns a reply containing a status string and a `decisions` list
    - _Requirements: 1.1, 2.1, 2.6_

- [x] 10. Final checkpoint — ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- The design uses Python throughout; all code targets the existing `strands`/`decider_kit` stack
- `HackathonAgent` is preserved as an alias so no other files in the kit need changes
- Property tests require `hypothesis` (`pip install hypothesis`); add it to `pyproject.toml` or `requirements.txt`
- Carrier clients in Task 1.4 are intentionally minimal stubs — fill in real HTTP calls when a sandbox API key is available
- All irreversible tools must appear in `ShippingActionGuard.GUARDED_TOOLS` to be protected by the guardrail
- The `CARRIER_API_KEY` redaction requirement (Property 7) must be verified by integration tests, not just unit tests

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.3"] },
    { "id": 1, "tasks": ["1.2", "1.4", "2.1", "9.1"] },
    { "id": 2, "tasks": ["1.5", "2.2", "4.1", "4.2"] },
    { "id": 3, "tasks": ["4.3", "4.4", "5.1"] },
    { "id": 4, "tasks": ["5.2", "6.1"] },
    { "id": 5, "tasks": ["6.2", "6.3", "6.4"] },
    { "id": 6, "tasks": ["8.1"] },
    { "id": 7, "tasks": ["8.2", "8.3", "9.2"] }
  ]
}
```
