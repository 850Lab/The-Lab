"""Workflow env readiness (phase diagnostics)."""

import pytest

import stripe_client
from services.workflow import env_readiness as er


@pytest.fixture(autouse=True)
def _clear_stripe_credential_cache():
    stripe_client._cached_credentials = None
    yield
    stripe_client._cached_credentials = None


def test_public_summary_all_ok_when_minimal_dev_env(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("REPLIT_DEPLOYMENT", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "a@b.com")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_x")
    monkeypatch.setenv("WORKFLOW_CUSTOMER_APP_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("LOB_API_KEY", "test_lob")
    monkeypatch.setenv("WORKFLOW_JOB_WORKER_ENABLED", "1")
    monkeypatch.delenv("REQUIRE_LOB_LIVE_FOR_CUSTOMER_SEND", raising=False)

    payload = er.compute_workflow_env_readiness(database_initialized_ok=True)
    summary = er.public_workflow_readiness_summary(payload)
    assert summary["allPhasesOperational"] is True
    assert summary["phaseCounts"]["blocked"] == 0


def test_payment_degraded_without_stripe(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("REPLIT_DEPLOYMENT", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "a@b.com")
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_PUBLISHABLE_KEY", raising=False)
    monkeypatch.setenv("WORKFLOW_CUSTOMER_APP_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("LOB_API_KEY", "test_lob")
    monkeypatch.delenv("REQUIRE_LOB_LIVE_FOR_CUSTOMER_SEND", raising=False)

    payload = er.compute_workflow_env_readiness(database_initialized_ok=True)
    pay = next(p for p in payload["linearPhases"] if p["id"] == "payment")
    assert pay["status"] == "degraded"


def test_parse_degraded_when_worker_disabled(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "a@b.com")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_x")
    monkeypatch.setenv("WORKFLOW_CUSTOMER_APP_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("LOB_API_KEY", "test_lob")
    monkeypatch.setenv("WORKFLOW_JOB_WORKER_ENABLED", "0")
    monkeypatch.delenv("REQUIRE_LOB_LIVE_FOR_CUSTOMER_SEND", raising=False)

    payload = er.compute_workflow_env_readiness(database_initialized_ok=True)
    parse_p = next(p for p in payload["linearPhases"] if p["id"] == "parse_analyze")
    assert parse_p["status"] == "degraded"


def test_production_blocked_without_database_url(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    payload = er.compute_workflow_env_readiness(database_initialized_ok=True)
    assert payload["summary"]["allPhasesOperational"] is False
    assert payload["integrations"]["database"]["status"] == "blocked"
