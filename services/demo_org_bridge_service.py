"""Demo lead → paying organization bridge (Mission Control / operator)."""

from __future__ import annotations

from typing import Any, Dict

import database as db
from services.org_service import create_organization


def convert_demo_lead_to_org(lead_id: int, organization_name: str) -> Dict[str, Any]:
    """
    Create a new organization and attach the demo lead row for continuity tracking.
    Does not create users or memberships (use existing admin APIs).
    """
    lead = db.get_demo_lead(int(lead_id))
    if not lead:
        return {"error": "Demo lead not found."}
    if lead.get("converted_organization_id"):
        return {"error": "This lead was already converted to an organization."}
    name = (organization_name or "").strip()[:255]
    if not name:
        return {"error": "Organization name is required."}
    org = create_organization(name, status="active")
    if org.get("error"):
        return {"error": str(org["error"])}
    oid = int(org["id"])
    if not db.link_demo_lead_to_organization(int(lead_id), oid):
        return {"error": "Could not link lead (race or already converted)."}
    return {"organization": org, "leadId": int(lead_id)}
