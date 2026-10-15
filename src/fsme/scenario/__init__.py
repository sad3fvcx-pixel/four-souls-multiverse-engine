# src/fsme/scenario/__init__.py

"""
Scenarios: the configuration a game starts from.

Plain data with no behaviour, deliberately knowing nothing about the engine.
The rules read a scenario; a scenario never reads the rules.
"""

from __future__ import annotations

from .errors import ScenarioError
from .file import load, parse, save, validate
from .library import Entry, Library, open_library
from .scenario import (
    FORMAT,
    VERSION,
    Content,
    Scenario,
    Seat,
    Table,
    digest_of,
    from_dict,
)

__all__ = [
    "Content",
    "Entry",
    "Library",
    "FORMAT",
    "Scenario",
    "ScenarioError",
    "Seat",
    "Table",
    "VERSION",
    "digest_of",
    "from_dict",
    "load",
    "open_library",
    "parse",
    "save",
    "validate",
]
