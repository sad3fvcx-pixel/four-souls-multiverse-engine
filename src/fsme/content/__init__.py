# src/fsme/content/__init__.py

"""
Content subsystem exports.

Official cards and somebody's homemade set load through the same pipeline and
get the same scrutiny. The engine has no privileged content.
"""

from .constants import (
    BASE_GAME_DIRECTORY,
    CARD_FILE_EXTENSION,
    CONTENT_SCHEMA_VERSION,
    CONTENT_SECTIONS,
    CUSTOM_DIRECTORY,
    EXPANSIONS_DIRECTORY,
    MANIFEST_NAME,
    USER_DIRECTORY,
)
from .errors import (
    ContentError,
    ContentLoadError,
    ContentNotFoundError,
    DuplicateContentError,
    InvalidContentError,
    MissingDependencyError,
)
from .library import ContentLibrary, Expansion
from .loader import ContentLoader
from .manifest import Manifest, validate_manifest
from .report import IssueCategory, ValidationIssue, ValidationReport
from .vocabulary import UNCHECKED, EffectShape, ParamShape, Vocabulary

__all__ = [
    "ContentLibrary",
    "ContentLoader",
    "Expansion",
    "IssueCategory",
    "Manifest",
    "ValidationIssue",
    "ValidationReport",
    "Vocabulary",
    "EffectShape",
    "ParamShape",
    "UNCHECKED",
    "validate_manifest",
    "ContentError",
    "ContentLoadError",
    "ContentNotFoundError",
    "DuplicateContentError",
    "InvalidContentError",
    "MissingDependencyError",
    "BASE_GAME_DIRECTORY",
    "CARD_FILE_EXTENSION",
    "CONTENT_SCHEMA_VERSION",
    "CONTENT_SECTIONS",
    "CUSTOM_DIRECTORY",
    "EXPANSIONS_DIRECTORY",
    "MANIFEST_NAME",
    "USER_DIRECTORY",
]
