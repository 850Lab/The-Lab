"""Thin Law Intelligence V1 — read-only legal reference attachment (strategy payload only)."""

from services.law_bank.load_corpus import load_published_units
from services.law_bank.resolve import resolve_law_units

__all__ = ["load_published_units", "resolve_law_units"]
