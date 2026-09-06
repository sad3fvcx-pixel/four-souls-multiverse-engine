# src/fsme/content/constants.py

"""
Constants used by the content subsystem.
"""

from __future__ import annotations

CONTENT_SCHEMA_VERSION = "1"
"""
The card and manifest schema this engine reads.

Content declares the schema it was written for, and a set written for a
different one is refused rather than half-understood.
"""

MANIFEST_NAME = "manifest.json"

CARD_FILE_EXTENSION = ".json"

DEFAULT_ENCODING = "utf-8"

BASE_GAME_DIRECTORY = "base_game"
EXPANSIONS_DIRECTORY = "expansions"
CUSTOM_DIRECTORY = "custom"
USER_DIRECTORY = "user"

CONTENT_SECTIONS = (
    BASE_GAME_DIRECTORY,
    EXPANSIONS_DIRECTORY,
    CUSTOM_DIRECTORY,
    USER_DIRECTORY,
)
"""
Where sets live under a content root.

The split is by origin, not by mechanics: official cards, published
expansions, community sets and a player's own work all load through the same
pipeline and get no special treatment from the engine.
"""
