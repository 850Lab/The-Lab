"""ORION V1.10 — audit snapshot and version surface."""

from __future__ import annotations

from services.guidance.orion_audit import audit_orion_bundle_for_workflow
from services.guidance.orion_versions import ORION_VERSIONS, orion_versions_for_audit_response


def test_orion_versions_stable_and_complete():
    v = orion_versions_for_audit_response()
    assert v == {
        "actionReadinessVersion": ORION_VERSIONS["action_readiness"],
        "actionExplanationVersion": ORION_VERSIONS["action_explanation"],
        "deliveryPrioritizationVersion": ORION_VERSIONS["delivery_prioritization"],
        "uxSurfaceContractVersion": ORION_VERSIONS["ux_surface_contract"],
    }
    assert all(isinstance(x, str) and "_v1" in x for x in v.values())


def test_audit_orion_bundle_empty_workflow_no_crash():
    snap = audit_orion_bundle_for_workflow("")
    assert snap["workflowId"] is None
    assert snap["guidance"] is None
    assert snap["bestAction"] is None
    assert snap["bestActionExplanation"] is None
    assert isinstance(snap["deliveryPrioritization"], dict)
    assert isinstance(snap["uxSurfaceContract"], dict)
    assert "timestamp" in snap
    assert snap["versions"] == orion_versions_for_audit_response()


def test_audit_orion_bundle_unknown_workflow_id_shape():
    snap = audit_orion_bundle_for_workflow("definitely-not-a-real-workflow-id-00000000")
    assert snap["workflowId"] == "definitely-not-a-real-workflow-id-00000000"
    assert snap["versions"] == orion_versions_for_audit_response()
    assert set(snap.keys()) == {
        "workflowId",
        "timestamp",
        "guidance",
        "bestAction",
        "bestActionExplanation",
        "deliveryPrioritization",
        "uxSurfaceContract",
        "versions",
    }
