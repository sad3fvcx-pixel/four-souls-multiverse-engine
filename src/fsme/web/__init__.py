# src/fsme/web/__init__.py

"""
The engine in a browser.
"""

from __future__ import annotations

from .server import GameServer, serve

__all__ = ["GameServer", "serve"]
