"""Sanity checks for trusted-path flow gate helpers (no DB)."""

from __future__ import annotations

from services.workflow.workflow_flow_gates import (
    assert_customer_payment_capture_allowed,
    assert_customer_payment_continue_credits_allowed,
    assert_internal_service_complete_allowed,
    assert_internal_service_fail_allowed,
)


def test_assert_helpers_reject_empty_workflow_id():
    assert assert_internal_service_complete_allowed("", "upload") is False
    assert assert_internal_service_complete_allowed("   ", "upload") is False
    assert assert_internal_service_fail_allowed("", "upload") is False
    assert assert_customer_payment_capture_allowed("") is False
    assert assert_customer_payment_continue_credits_allowed("") is False
