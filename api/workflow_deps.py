"""
FastAPI dependencies: session auth + workflow ownership.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.workflow.repository import fetch_session

_bearer = HTTPBearer(auto_error=False)


def get_workflow_internal_secret() -> str:
    return (os.environ.get("WORKFLOW_INTERNAL_API_SECRET") or "").strip()


def get_workflow_admin_secret() -> str:
    return (os.environ.get("WORKFLOW_ADMIN_API_SECRET") or "").strip()


def require_internal_service(
    x_workflow_internal_key: Optional[str] = Header(None, alias="X-Workflow-Internal-Key"),
    authorization: Optional[str] = Header(None),
) -> None:
    """Workers / other services must send the configured secret."""
    secret = get_workflow_internal_secret()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="WORKFLOW_INTERNAL_API_SECRET is not configured",
        )
    if x_workflow_internal_key and x_workflow_internal_key == secret:
        return
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        if token == secret:
            return
    raise HTTPException(status_code=403, detail="Invalid internal workflow credentials")


def require_admin_service(
    x_workflow_admin_key: Optional[str] = Header(None, alias="X-Workflow-Admin-Key"),
    authorization: Optional[str] = Header(None),
) -> None:
    """
    Admin / operator routes only. Uses WORKFLOW_ADMIN_API_SECRET (never the internal worker secret).
    Accepts ``X-Workflow-Admin-Key`` or ``Authorization: Bearer <admin secret>``.
    """
    secret = get_workflow_admin_secret()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="WORKFLOW_ADMIN_API_SECRET is not configured",
        )
    if x_workflow_admin_key and x_workflow_admin_key == secret:
        return
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        if token == secret:
            return
    raise HTTPException(status_code=403, detail="Invalid admin workflow credentials")


def get_session_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Dict[str, Any]:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "AUTH_REQUIRED",
                "messageSafe": "Authorization Bearer token required.",
            },
        )
    import auth

    user = auth.validate_session(creds.credentials)
    if not user:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INVALID_SESSION",
                "messageSafe": "Session expired or invalid.",
            },
        )
    return user


def get_session_bearer_token(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> str:
    """Raw bearer token string for logout and other token-scoped actions."""
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "AUTH_REQUIRED",
                "messageSafe": "Authorization Bearer token required.",
            },
        )
    return creds.credentials.strip()


def get_owned_workflow(
    workflow_id: str,
    user: Dict[str, Any] = Depends(get_session_user),
) -> Dict[str, Any]:
    row = fetch_session(workflow_id)
    if not row:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "NOT_FOUND",
                "messageSafe": "Workflow not found.",
            },
        )
    if int(row["user_id"]) != int(user["user_id"]):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "WORKFLOW_ACCESS_DENIED",
                "messageSafe": "This workflow does not belong to the signed-in user.",
            },
        )
    return row
