# src/fsme/lab/desk/__init__.py

"""
The front door: everything FSME does, on one page.
"""

from __future__ import annotations

from .bench import Job, Workbench
from .server import DeskHandler, DeskServer, desk

__all__ = ["DeskHandler", "DeskServer", "Job", "Workbench", "desk"]
