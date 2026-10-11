# src/fsme/database/__init__.py

"""
Database subsystem exports.

Indexing over loaded content. It holds no gameplay state and answers questions
about definitions, never about a game in progress.
"""

from .database import ContentIndex

__all__ = ["ContentIndex"]
