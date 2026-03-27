"""
Gilbertus → Omnius client.

Provides READ + WRITE + ADMIN access to any Omnius tenant.
Used by Gilbertus to manage corporate AI agents.

Usage:
    client = OmniusClient("reh")
    result = client.ask("jaki jest status projektu BESS?")
    client.create_ticket("Follow up na kontrakt NOFAR", assignee="roch")
    client.send_email(to="roch@respect.energy", subject="Reminder", body="...")
"""
from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()


class OmniusClient:
    """Client for communicating with an Omnius tenant."""

    def __init__(self, tenant: str):
        self.tenant = tenant.lower()
        self.base_url = os.getenv(f"OMNIUS_{self.tenant.upper()}_URL", f"http://localhost:800{1 if tenant == 'reh' else 2}")
        self.api_key = os.getenv(f"OMNIUS_{self.tenant.upper()}_ADMIN_KEY", "")
        self.timeout = 60

    def _headers(self) -> dict:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        resp = requests.get(f"{self.base_url}{path}", headers=self._headers(), params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: dict | None = None) -> dict[str, Any]:
        resp = requests.post(f"{self.base_url}{path}", headers=self._headers(), json=data, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    # ================================================================
    # READ operations
    # ================================================================

    def health(self) -> dict[str, Any]:
        return self._get("/health")

    def ask(self, query: str, answer_length: str = "long") -> dict[str, Any]:
        return self._post("/ask", {"query": query, "answer_length": answer_length})

    def status(self) -> dict[str, Any]:
        return self._get("/status")

    def timeline(self, event_type: str | None = None, date_from: str | None = None, date_to: str | None = None, limit: int = 10) -> dict[str, Any]:
        params = {"limit": limit}
        if event_type:
            params["event_type"] = event_type
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        return self._post("/timeline", params)

    def summary(self, date: str, summary_type: str = "daily", areas: list[str] | None = None) -> dict[str, Any]:
        return self._post("/summary/generate", {"date": date, "summary_type": summary_type, "areas": areas or ["general"]})

    def get_nightly_report(self) -> dict[str, Any]:
        """Get aggregated report for Gilbertus morning brief."""
        return self._get("/report/nightly")

    # ================================================================
    # WRITE operations (commands)
    # ================================================================

    def create_ticket(self, title: str, description: str = "", assignee: str | None = None, priority: str = "medium") -> dict[str, Any]:
        return self._post("/commands/create_ticket", {
            "title": title, "description": description,
            "assignee": assignee, "priority": priority,
        })

    def send_email(self, to: str, subject: str, body: str, cc: list[str] | None = None) -> dict[str, Any]:
        return self._post("/commands/send_email", {
            "to": to, "subject": subject, "body": body, "cc": cc or [],
        })

    def schedule_meeting(self, subject: str, attendees: list[str], start: str, end: str, body: str = "") -> dict[str, Any]:
        return self._post("/commands/schedule_meeting", {
            "subject": subject, "attendees": attendees,
            "start": start, "end": end, "body": body,
        })

    def assign_task(self, description: str, assignee: str, deadline: str | None = None, priority: str = "medium") -> dict[str, Any]:
        return self._post("/commands/assign_task", {
            "description": description, "assignee": assignee,
            "deadline": deadline, "priority": priority,
        })

    # ================================================================
    # ADMIN operations
    # ================================================================

    def create_user(self, username: str, role: str = "user") -> dict[str, Any]:
        return self._post("/admin/users", {"username": username, "role": role})

    def list_users(self) -> dict[str, Any]:
        return self._get("/admin/users")

    def update_config(self, key: str, value: Any) -> dict[str, Any]:
        return self._post("/admin/config", {"key": key, "value": value})

    def trigger_sync(self, source: str = "all") -> dict[str, Any]:
        """Trigger data sync (SharePoint, Teams, etc.)."""
        return self._post("/admin/sync", {"source": source})

    def get_extraction_status(self) -> dict[str, Any]:
        return self._get("/admin/extraction/status")


# ================================================================
# Multi-tenant manager
# ================================================================

_clients: dict[str, OmniusClient] = {}

def get_omnius(tenant: str) -> OmniusClient:
    """Get or create an Omnius client for a tenant."""
    if tenant not in _clients:
        _clients[tenant] = OmniusClient(tenant)
    return _clients[tenant]


def list_tenants() -> list[str]:
    """List configured Omnius tenants from env."""
    tenants = []
    for key in os.environ:
        if key.startswith("OMNIUS_") and key.endswith("_URL"):
            tenant = key.replace("OMNIUS_", "").replace("_URL", "").lower()
            tenants.append(tenant)
    return tenants
