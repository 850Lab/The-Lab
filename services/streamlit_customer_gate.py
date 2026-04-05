"""
Customer-facing mutation authority: **React + FastAPI** (`api/workflow_app.py`).

Streamlit (`app.py`) is legacy. When this gate is active, Streamlit must not persist
reports or advance workflow via interactive paths. Operators may set
``STREAMLIT_ALLOW_CUSTOMER_MUTATIONS=1`` to temporarily re-enable legacy behavior
(non-production or production escape hatch).

Payment return URLs that still hit Streamlit are exempted in ``hooks`` only for
``audit_source`` values containing ``payment_return`` so credits are not stranded
while success URLs are migrated to the SPA.
"""

from __future__ import annotations

import os

from services.workflow.workflow_db_config import is_production_like


def streamlit_customer_mutations_forbidden() -> bool:
    explicit = (os.environ.get("STREAMLIT_CUSTOMER_READ_ONLY") or "").strip().lower()
    if explicit in ("1", "true", "yes", "on"):
        return True
    if is_production_like():
        allow = (os.environ.get("STREAMLIT_ALLOW_CUSTOMER_MUTATIONS") or "").strip().lower()
        if allow not in ("1", "true", "yes", "on"):
            return True
    return False


def streamlit_customer_product_shell_disabled() -> bool:
    """When True, non-admin users should not enter the legacy dispute workflow shell."""
    return streamlit_customer_mutations_forbidden()


def streamlit_workflow_hook_mutations_disabled() -> bool:
    """True when hook layer should no-op Streamlit-branded interactive mutations."""
    legacy = (os.environ.get("STREAMLIT_WORKFLOW_MUTATIONS_DISABLED") or "").strip().lower()
    if legacy in ("1", "true", "yes", "on"):
        return True
    return streamlit_customer_mutations_forbidden()
