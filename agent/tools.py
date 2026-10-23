"""Shipping-tracking agent tools.

REUSABLE DECISION PATTERN: #model-routing (model routing for shipping queries)

Tools are grouped into:
  - Read-only: lookup_shipment, list_cached_shipments
  - Damage reporting: report_damage  (reversible — collects data only)
  - Irreversible: initiate_carrier_investigation, request_replacement,
                  initiate_refund, request_address_change

The four irreversible tools are guarded by ShippingActionGuard (agent/decision.py),
which requires Decider confirmation before execution.

Session state (identifier cache, shipment cache) lives in SessionStore (agent/session.py).
The active session is set by ShippingTrackingAgent before each Agent invocation via
the module-level set_current_session() helper.
"""
from __future__ import annotations

import re
from contextvars import ContextVar
from typing import Any

from strands import tool

from agent.carrier import CarrierAPIError, CarrierClient
from agent.models import Address, AddressChangeResult
from agent.session import SessionStore

# ── session context ──────────────────────────────────────────────────────────
# ShippingTrackingAgent calls set_current_session(store, carrier) before each
# agent invocation so that all tools in this module share the same context.

_current_session: ContextVar[SessionStore | None] = ContextVar("_current_session", default=None)
_current_carrier: ContextVar[CarrierClient | None] = ContextVar("_current_carrier", default=None)


def set_current_session(store: SessionStore, carrier: CarrierClient) -> None:
    """Called by ShippingTrackingAgent before each chat turn."""
    _current_session.set(store)
    _current_carrier.set(carrier)


def _session() -> SessionStore:
    s = _current_session.get()
    if s is None:
        raise RuntimeError("No active session — call set_current_session() before invoking tools")
    return s


def _carrier() -> CarrierClient:
    c = _current_carrier.get()
    if c is None:
        raise RuntimeError("No active carrier — call set_current_session() before invoking tools")
    return c


# ── helpers ───────────────────────────────────────────────────────────────────

def _format_shipment_status(shipment) -> str:
    """Human-readable single-sentence status for the customer (Req 1.2)."""
    latest = shipment.latest_event
    if latest:
        return (
            f"Your shipment ({shipment.tracking_number}) via {shipment.carrier} "
            f"is currently '{shipment.status}'. "
            f"Latest update: {latest.description} at {latest.location} "
            f"on {latest.timestamp.strftime('%Y-%m-%d %H:%M UTC')}."
        )
    eta = shipment.estimated_delivery
    eta_str = eta.strftime("%Y-%m-%d") if eta else "unknown"
    return (
        f"Your shipment ({shipment.tracking_number}) via {shipment.carrier} "
        f"is currently '{shipment.status}'. Estimated delivery: {eta_str}."
    )


# ── read-only tools ───────────────────────────────────────────────────────────

@tool
def lookup_shipment(identifier: str) -> dict:
    """Look up the current status of a shipment by tracking number or order ID."""
    identifier = identifier.strip()
    store = _session()
    store.add_identifier(identifier)

    # Return cached data if still fresh
    if not store.needs_refresh(identifier):
        shipment = store.get_shipment(identifier)
        if shipment is not None:
            return {
                "tracking_number": shipment.tracking_number,
                "carrier": shipment.carrier,
                "status": shipment.status,
                "estimated_delivery": (
                    shipment.estimated_delivery.isoformat()
                    if shipment.estimated_delivery else None
                ),
                "latest_event": (
                    {
                        "description": shipment.latest_event.description,
                        "location": shipment.latest_event.location,
                        "timestamp": shipment.latest_event.timestamp.isoformat(),
                    }
                    if shipment.latest_event else None
                ),
                "is_exception": shipment.is_exception,
                "days_overdue": shipment.days_since_estimated_delivery(),
                "source": "cache",
            }

    # Cache miss or stale — query carrier API
    try:
        shipment = _carrier().get_shipment(identifier)
    except CarrierAPIError as exc:
        return {"error": "carrier_unavailable", "message": str(exc), "retry_after_minutes": 15}

    if shipment is None:
        return {"error": "tracking_not_found", "identifier": identifier,
                "message": f"No shipment found for '{identifier}'. Please verify the tracking number."}

    store.put_shipment(identifier, shipment)
    return {
        "tracking_number": shipment.tracking_number,
        "carrier": shipment.carrier,
        "status": shipment.status,
        "estimated_delivery": (
            shipment.estimated_delivery.isoformat() if shipment.estimated_delivery else None
        ),
        "latest_event": (
            {
                "description": shipment.latest_event.description,
                "location": shipment.latest_event.location,
                "timestamp": shipment.latest_event.timestamp.isoformat(),
            }
            if shipment.latest_event else None
        ),
        "is_exception": shipment.is_exception,
        "days_overdue": shipment.days_since_estimated_delivery(),
        "source": "live",
    }


@tool
def list_cached_shipments() -> dict:
    """List all tracking numbers remembered in the current session."""
    store = _session()
    return {"identifiers": store.identifiers(), "count": len(store)}


# ── damage report tool (reversible — data collection only) ───────────────────

@tool
def report_damage(order_id: str, description: str) -> dict:
    """Collect a damage report for an order; does not initiate any refund or replacement."""
    order_id = (order_id or "").strip()
    description = (description or "").strip()

    # Validate order_id: 1–20 alphanumeric chars (Req 1.1)
    if not order_id or not re.match(r"^[A-Za-z0-9]{1,20}$", order_id):
        return {
            "error": "invalid_order_id",
            "message": "order_id must be 1–20 alphanumeric characters. Please provide a valid order ID.",
        }

    # Validate description: 1–1000 chars (Req 3.4)
    if not description:
        return {
            "error": "invalid_description",
            "message": "Please describe the damage (up to 1000 characters).",
        }
    if len(description) > 1000:
        return {
            "error": "invalid_description",
            "message": f"Description is too long ({len(description)} chars). Please keep it under 1000 characters.",
        }

    return {
        "status": "damage_reported",
        "order_id": order_id,
        "description": description,
        "next_steps": "Please choose a resolution: 'replacement' or 'refund'.",
    }


# ── irreversible action tools (guarded by ShippingActionGuard) ───────────────

@tool
def initiate_carrier_investigation(tracking_no: str) -> dict:
    """Open a lost-package investigation with the carrier (irreversible)."""
    tracking_no = (tracking_no or "").strip()
    if not tracking_no:
        return {"error": "missing_tracking_number", "message": "A tracking number is required."}

    # In a production integration this would call the carrier API.
    # This implementation records the investigation request in the session.
    store = _session()
    store.add_identifier(tracking_no)
    return {
        "status": "investigation_initiated",
        "tracking_number": tracking_no,
        "message": (
            f"A carrier investigation has been opened for shipment {tracking_no}. "
            "The carrier will respond within 3–5 business days."
        ),
        "reference": f"INV-{tracking_no[:8].upper()}",
    }


@tool
def request_replacement(order_id: str) -> dict:
    """Request a replacement item for a damaged or lost order (irreversible)."""
    order_id = (order_id or "").strip()
    if not order_id or not re.match(r"^[A-Za-z0-9]{1,20}$", order_id):
        return {"error": "invalid_order_id",
                "message": "A valid order ID (1–20 alphanumeric characters) is required."}

    return {
        "status": "replacement_requested",
        "order_id": order_id,
        "message": (
            f"A replacement for order {order_id} has been requested. "
            "You will receive a new tracking number by email within 1 business day."
        ),
        "reference": f"REP-{order_id.upper()}",
    }


@tool
def initiate_refund(order_id: str, amount: float) -> dict:
    """Issue a refund for an order (irreversible)."""
    order_id = (order_id or "").strip()
    if not order_id or not re.match(r"^[A-Za-z0-9]{1,20}$", order_id):
        return {"error": "invalid_order_id",
                "message": "A valid order ID (1–20 alphanumeric characters) is required."}

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {"error": "invalid_amount", "message": "Amount must be a positive number."}

    if amount <= 0:
        return {"error": "invalid_amount", "message": "Refund amount must be greater than zero."}

    return {
        "status": "refund_initiated",
        "order_id": order_id,
        "amount": round(amount, 2),
        "message": (
            f"A refund of ${amount:.2f} for order {order_id} has been initiated. "
            "It will appear on your payment method within 3–5 business days."
        ),
        "reference": f"REF-{order_id.upper()}",
    }


@tool
def request_address_change(tracking_no: str, street: str, city: str, postal_code: str, country: str, state: str = "") -> dict:
    """Request a delivery address change for an in-transit shipment (irreversible)."""
    tracking_no = (tracking_no or "").strip()
    if not tracking_no:
        return {"error": "missing_tracking_number", "message": "A tracking number is required."}

    new_address = Address(
        street=(street or "").strip(),
        city=(city or "").strip(),
        postal_code=(postal_code or "").strip(),
        country=(country or "").strip(),
        state=(state or "").strip() or None,
    )

    if not new_address.is_complete():
        missing = [f for f in ("street", "city", "postal_code", "country")
                   if not getattr(new_address, f)]
        return {
            "error": "incomplete_address",
            "missing_fields": missing,
            "message": f"Address is missing required fields: {', '.join(missing)}. Please provide all of: street, city, postal_code, country.",
        }

    try:
        result: AddressChangeResult = _carrier().change_address(tracking_no, new_address)
    except CarrierAPIError as exc:
        return {"error": "carrier_error", "message": str(exc), "suggestion": "Please retry or contact the carrier directly."}

    if result.success:
        return {
            "status": "address_changed",
            "tracking_number": tracking_no,
            "new_address": new_address.__dict__,
            "revised_eta": result.revised_eta.isoformat() if result.revised_eta else None,
            "message": f"Delivery address for {tracking_no} has been updated successfully.",
        }
    return {
        "status": "address_change_failed",
        "tracking_number": tracking_no,
        "error_reason": result.error_reason,
        "message": (
            f"Address change could not be completed: {result.error_reason}. "
            "You may request a hold at the carrier facility or contact the carrier directly."
        ),
    }


TOOLS = [
    lookup_shipment,
    list_cached_shipments,
    report_damage,
    initiate_carrier_investigation,
    request_replacement,
    initiate_refund,
    request_address_change,
]

IRREVERSIBLE_TOOLS = {
    "initiate_carrier_investigation",
    "request_replacement",
    "initiate_refund",
    "request_address_change",
}
