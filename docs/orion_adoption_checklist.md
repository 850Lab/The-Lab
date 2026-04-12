# ORION adoption checklist (customer workflow pages)

Use this when adding or changing a step page so narrative and contracts stay aligned with O.R.I.O.N.

- [ ] Page reads `orionViewModel` from `CustomerWorkflowContext` (or equivalent parent).
- [ ] Hero / primary story defers to `resolveOrionAuthority` + `orionStepHeroCopy` (or other shared ORION helpers) when a contract exists; local copy is fallback only.
- [ ] Rendering uses `resolvePrimaryRenderable` / `resolveSupportingRenderables` (or pre-built `primaryRenderable` on the view model) instead of re-deriving priority from raw `bestAction` when `contractCompleteness` is `full`.
- [ ] Page does not introduce competing generic “what’s next” blocks when ORION `full_contract` already states posture (see `orionNarrativeCoherent` pattern on reference pages).
- [ ] Integrity (`integrityHints` / `WorkflowIntegrityBanner`) is treated as **blocking and constraint**, not as a second narrator when ORION is primary and hints are soft.
- [ ] Root layout includes `data-orion-fallback={orionViewModel.fallbackMode}` (or the resolved fallback mode) for observability.
- [ ] No AI or LLM calls inside ORION normalization (`orionViewModel`, `orionAuthority`); AI may only consume ORION outputs downstream.

This document is not executed at runtime; it is a guardrail for human and agent reviewers.
