"""
Execution guidance blocks — user participation layer (Capability 5).
"""

from __future__ import annotations

from .compiler import (
    PATH_DOCS_THIN,
    SCHEMA_VERSION,
    SPA_PATH_IDS,
    build_execution_guidance_bundle,
    build_execution_guidance_for_workflow,
    resolve_playbook_id,
)
from .models import ExecutionGuidanceBlock, ExecutionGuidanceBundle, ParallelGroup
from .signals import SignalCaptureTarget, VerificationFailureSeverity
from .triggers import TimingTrigger

__all__ = [
    "PATH_DOCS_THIN",
    "SCHEMA_VERSION",
    "SPA_PATH_IDS",
    "ExecutionGuidanceBlock",
    "ExecutionGuidanceBundle",
    "ParallelGroup",
    "SignalCaptureTarget",
    "TimingTrigger",
    "VerificationFailureSeverity",
    "build_execution_guidance_bundle",
    "build_execution_guidance_for_workflow",
    "resolve_playbook_id",
]
