"""Compatibility import; Ticket persistence is owned by the final Ticket module."""

from backend.apps.support_api.tickets.repository import PostgresTicketRepository

__all__ = ["PostgresTicketRepository"]
