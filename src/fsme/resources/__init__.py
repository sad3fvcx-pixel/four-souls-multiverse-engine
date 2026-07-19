# src/fsme/resources/__init__.py

"""
Resource subsystem exports.
"""

from .constants import (
    AUDIO_EXTENSIONS,
    DEFAULT_AUDIO_DIRECTORY,
    DEFAULT_CARD_DIRECTORY,
    DEFAULT_CONTENT_DIRECTORY,
    DEFAULT_IMAGE_DIRECTORY,
    DEFAULT_LOCALE_DIRECTORY,
    DEFAULT_RESOURCE_DIRECTORY,
    IMAGE_EXTENSIONS,
    JPEG_EXTENSION,
    JPG_EXTENSION,
    JSON_EXTENSION,
    JSON_EXTENSIONS,
    MP3_EXTENSION,
    OGG_EXTENSION,
    PNG_EXTENSION,
    RESOURCE_TYPE_AUDIO,
    RESOURCE_TYPE_CARD,
    RESOURCE_TYPE_CONTENT,
    RESOURCE_TYPE_GENERIC,
    RESOURCE_TYPE_IMAGE,
    RESOURCE_TYPE_LOCALE,
    SVG_EXTENSION,
    TEXT_EXTENSIONS,
    WAV_EXTENSION,
    WEBP_EXTENSION,
    YAML_EXTENSION,
    YAML_EXTENSIONS,
    YML_EXTENSION,
)
from .context import ResourceContext
from .errors import (
    ResourceAlreadyExistsError,
    ResourceError,
    ResourceLoadError,
    ResourceNotFoundError,
    ResourceTypeError,
    ResourceValidationError,
)
from .loader import ResourceLoader
from .manager import ResourceManager
from .registry import ResourceRegistry
from .resource import Resource
from .result import ResourceResult
from .utils import (
    ensure_resource,
    is_resource,
    normalize_path,
    resource_exists,
    resource_name,
    resource_stem,
    resource_suffix,
)

__all__ = [
    "Resource",
    "ResourceRegistry",
    "ResourceLoader",
    "ResourceManager",
    "ResourceContext",
    "ResourceResult",
    "ResourceError",
    "ResourceNotFoundError",
    "ResourceAlreadyExistsError",
    "ResourceLoadError",
    "ResourceValidationError",
    "ResourceTypeError",
    "DEFAULT_RESOURCE_DIRECTORY",
    "DEFAULT_CONTENT_DIRECTORY",
    "DEFAULT_CARD_DIRECTORY",
    "DEFAULT_IMAGE_DIRECTORY",
    "DEFAULT_LOCALE_DIRECTORY",
    "DEFAULT_AUDIO_DIRECTORY",
    "RESOURCE_TYPE_GENERIC",
    "RESOURCE_TYPE_CARD",
    "RESOURCE_TYPE_CONTENT",
    "RESOURCE_TYPE_IMAGE",
    "RESOURCE_TYPE_LOCALE",
    "RESOURCE_TYPE_AUDIO",
    "JSON_EXTENSION",
    "YAML_EXTENSION",
    "YML_EXTENSION",
    "PNG_EXTENSION",
    "JPG_EXTENSION",
    "JPEG_EXTENSION",
    "WEBP_EXTENSION",
    "SVG_EXTENSION",
    "OGG_EXTENSION",
    "WAV_EXTENSION",
    "MP3_EXTENSION",
    "JSON_EXTENSIONS",
    "YAML_EXTENSIONS",
    "IMAGE_EXTENSIONS",
    "AUDIO_EXTENSIONS",
    "TEXT_EXTENSIONS",
    "is_resource",
    "ensure_resource",
    "normalize_path",
    "resource_name",
    "resource_stem",
    "resource_suffix",
    "resource_exists",
]
