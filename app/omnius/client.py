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

    def create_user(self, email: str, display_name: str, role: str = "specialist",
                    department: str | None = None) -> dict[str, Any]:
        return self._post("/admin/users", {
            "email": email, "display_name": display_name,
            "role": role, "department": department,
        })

    def list_users(self) -> dict[str, Any]:
        return self._get("/admin/users")

    def update_config(self, key: str, value: Any) -> dict[str, Any]:
        return self._post("/admin/config", {"key": key, "value": value})

    def trigger_sync(self, source: str = "all") -> dict[str, Any]:
        """Trigger data sync (SharePoint, Teams, etc.)."""
        return self._post("/admin/sync", {"source": source})

    def get_extraction_status(self) -> dict[str, Any]:
        return self._get("/admin/extraction/status")

    def push_permissions(self, role: str, permissions: list[str]) -> dict[str, Any]:
        """Push RBAC permissions for a role from Gilbertus."""
        return self._post("/admin/config", {
            "key": f"rbac:permissions:{role}",
            "value": permissions,
        })

    def push_prompt(self, prompt_name: str, prompt_text: str) -> dict[str, Any]:
        """Push system prompt from Gilbertus."""
        return self._post("/admin/config", {
            "key": f"prompt:{prompt_name}",
            "value": prompt_text,
        })

    def get_audit_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent audit log entries."""
        return self._get("/admin/audit", params={"limit": limit})

    def create_operator_task(self, title: str, description: str = "",
                             assignee_email: str = "michal.schulta@re-fuels.com") -> dict[str, Any]:
        """Create a task for the human operator."""
        return self._post("/admin/operator-tasks", {
            "title": title, "description": description,
            "assignee_email": assignee_email,
        })

    def list_operator_tasks(self, status: str = "pending") -> list[dict[str, Any]]:
        """List operator tasks by status."""
        return self._get("/admin/operator-tasks", params={"status": status})

    def create_api_key(self, name: str, role: str, user_email: str | None = None) -> dict[str, Any]:
        """Create an API key. Returns the key ONCE."""
        return self._post("/admin/api-keys", {
            "name": name, "role": role, "user_email": user_email,
        })

    def deploy(self) -> dict[str, Any]:
        """Deploy latest code to this tenant's server via rsync + SSH.

        Runs scripts/deploy_omnius.sh which:
        1. rsync omnius/ to remote server
        2. Runs DB migrations
        3. Rebuilds Docker containers
        4. Health check
        """
        import subprocess

        script = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "deploy_omnius.sh")
        script = os.path.abspath(script)

        try:
            result = subprocess.run(
                ["bash", script, self.tenant],
                capture_output=True, text=True, timeout=300,
                cwd=os.path.dirname(script),
            )
            return {
                "status": "ok" if result.returncode == 0 else "error",
                "returncode": result.returncode,
                "stdout": result.stdout[-2000:] if result.stdout else "",
                "stderr": result.stderr[-500:] if result.stderr else "",
            }
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "Deploy timed out after 300s"}
        except Exception as e:
            return {"status": "error", "error": str(e)}


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
