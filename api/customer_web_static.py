"""
Serve ``web/dist`` from the workflow API so Replit (and other hosts) can open the
customer React app on **port 8000** without running Vite.

Also strips ``/workflow-api`` from incoming paths so production bundles that use
``workflowApiBase() -> "/workflow-api"`` still hit ``/api/...`` on this server.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request

_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
_ASSETS = _DIST / "assets"


class StripWorkflowApiPrefixMiddleware(BaseHTTPMiddleware):
    """Map ``/workflow-api/api/...`` → ``/api/...`` (same as Vite dev proxy)."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ):
        path = request.url.path
        if path.startswith("/workflow-api"):
            new_path = path[len("/workflow-api") :] or "/"
            request.scope["path"] = new_path
            request.scope["raw_path"] = new_path.encode("utf-8")
        return await call_next(request)


def install_strip_workflow_api_prefix_middleware(app: FastAPI) -> None:
    app.add_middleware(StripWorkflowApiPrefixMiddleware)


def register_customer_web_status_route(app: FastAPI) -> None:
    """Always-on probe so Replit/deploy hosts can confirm dist + routing (no auth)."""

    @app.get("/api/system/customer-web-status", include_in_schema=False)
    def customer_web_status() -> dict[str, object]:
        idx = _DIST / "index.html"
        return {
            "ok": True,
            "dist_index_exists": idx.is_file(),
            "assets_dir_exists": _ASSETS.is_dir(),
            "dist_path": str(_DIST),
            "hint": "If dist_index_exists is false, run: cd web && npm install && npm run build",
        }


def mount_customer_web_dist_if_present(app: FastAPI, logger: logging.Logger) -> None:
    if not _DIST.is_dir() or not (_DIST / "index.html").is_file():
        logger.warning(
            "Customer web dist missing at %s — open web on port 5173 (npm run dev) "
            "or run: cd web && npm run build",
            _DIST,
        )
        return

    if _ASSETS.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(_ASSETS)),
            name="customer_web_assets",
        )

    @app.get("/", include_in_schema=False)
    async def _customer_spa_root() -> FileResponse:
        return FileResponse(_DIST / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _customer_spa_fallback(full_path: str) -> FileResponse:
        # Do not mask API, internal tools, or hashed assets (mount handles real files).
        if (
            full_path.startswith("api/")
            or full_path.startswith("internal/")
            or full_path.startswith("assets/")
        ):
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(_DIST / "index.html")
