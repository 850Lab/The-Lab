"""
850 Lab Report Scanners

One bureau, one scanner. No cross-bureau logic.
Same Truth Sheet, different layouts.

Supported:
- TransUnion: Full scanning
- Experian: Full scanning
- Equifax: Not yet active (handler only)
"""

from .transunion_scanner import TransUnionScanner, scan_transunion_report
from .experian_scanner import ExperianScanner, scan_experian_report
from .equifax_handler import EquifaxHandler, handle_equifax_report
