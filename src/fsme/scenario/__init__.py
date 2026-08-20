# src/fsme/scenario/__init__.py

"""
Scenarios: the configuration a game starts from.

Plain data with no behaviour, deliberately knowing nothing about the engine.
The rules read a scenario; a scenario never reads the rules.
"""

from __future__ import annotations

from .errors import ScenarioError
from .file import load, parse, save, validate
from .scenario import FORMAT, VERSION, Content, Scenario, Seat, Table, from_dict

__all__ = [
    "Content",
    "FORMAT",
    "Scenario",
    "ScenarioError",
    "Seat",
    "Table",
    "VERSION",
    "from_dict",
    "load",
    "parse",
    "save",
    "validate",
]
