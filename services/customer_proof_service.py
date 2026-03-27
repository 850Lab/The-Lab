"""
Customer proof step: DB-backed ID + address proof + signature (same paths as Streamlit ``views.legal``).

Workflow completion is driven by ``hooks.maybe_notify_proof_attachment_completed`` after each save.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import database as db
from services.workflow.engine import compute_authoritative_step
from services.workflow.repository import fetch_steps


def proof_attachment_head_state(workflow_id: str) -> Tuple[Optional[str], str, Optional[Dict[str, Any]]]:
    steps = fetch_steps(workflow_id)
    smap = {s["step_id"]: s for s in steps}
    head, phase = compute_authoritative_step(smap)
    row = smap.get("proof_attachment")
    return head, phase, row


def _iso(dt: Any) -> str:
    if dt is None:
        return ""
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def _summarize_doc_row(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "fileName": row.get("file_name") or "",
        "fileType": row.get("file_type") or "",
        "docType": row.get("doc_type") or "",
        "createdAt": _iso(row.get("created_at")),
    }


def build_proof_context_payload(user_id: int, workflow_id: str) -> Dict[str, Any]:
    """Serializable proof + step flags for React (no file bytes)."""
    hp = db.has_proof_docs(user_id)
    id_rows = db.get_proof_docs_for_user(user_id, doc_types=["government_id"])
    addr_rows = db.get_proof_docs_for_user(user_id, doc_types=["address_proof"])
    sig = db.get_user_signature(user_id)
    has_sig = sig is not None and len(sig) > 0

    head, phase, proof_row = proof_attachment_head_state(workflow_id)
    proof_status = (proof_row or {}).get("status")

    all_met = bool(hp.get("both")) and has_sig

    return {
        "hasGovernmentId": bool(hp.get("has_id")),
        "hasAddressProof": bool(hp.get("has_address")),
        "hasSignature": has_sig,
        "governmentId": _summarize_doc_row(id_rows[0] if id_rows else None),
        "addressProof": _summarize_doc_row(addr_rows[0] if addr_rows else None),
        "workflowHeadStepId": head,
        "workflowPhase": phase,
        "proofStepStatus": proof_status,
        "proofStepCompleted": proof_status == "completed",
        "onProofAttachmentStep": head == "proof_attachment" and phase == "active",
        "allRequirementsMet": all_met,
    }


def on_proof_attachment_step(workflow_id: str) -> bool:
    head, phase, _ = proof_attachment_head_state(workflow_id)
    return phase != "done" and head == "proof_attachment"
