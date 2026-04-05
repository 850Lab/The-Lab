"""Policy tests for ``services.streamlit_customer_gate`` (no DB required)."""

from __future__ import annotations

from importlib import reload


def test_explicit_readonly(monkeypatch):
    monkeypatch.setenv("STREAMLIT_CUSTOMER_READ_ONLY", "1")
    monkeypatch.delenv("REPLIT_DEPLOYMENT", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    import services.streamlit_customer_gate as g

    reload(g)
    assert g.streamlit_customer_mutations_forbidden()


def test_production_like_forbids_without_allow(monkeypatch):
    monkeypatch.delenv("STREAMLIT_CUSTOMER_READ_ONLY", raising=False)
    monkeypatch.delenv("STREAMLIT_ALLOW_CUSTOMER_MUTATIONS", raising=False)
    monkeypatch.setenv("REPLIT_DEPLOYMENT", "1")
    import services.streamlit_customer_gate as g

    reload(g)
    assert g.streamlit_customer_mutations_forbidden()


def test_production_like_allowed_with_explicit_flag(monkeypatch):
    monkeypatch.delenv("STREAMLIT_CUSTOMER_READ_ONLY", raising=False)
    monkeypatch.setenv("REPLIT_DEPLOYMENT", "1")
    monkeypatch.setenv("STREAMLIT_ALLOW_CUSTOMER_MUTATIONS", "1")
    import services.streamlit_customer_gate as g

    reload(g)
    assert not g.streamlit_customer_mutations_forbidden()
