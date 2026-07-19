# src/fsme/resources/constants.py

"""
Constants for the resource subsystem.
"""

from __future__ import annotations

from pathlib import Path

# Default resource directories

DEFAULT_RESOURCE_DIRECTORY = Path("resources")

DEFAULT_CONTENT_DIRECTORY = DEFAULT_RESOURCE_DIRECTORY / "content"

DEFAULT_CARD_DIRECTORY = DEFAULT_RESOURCE_DIRECTORY / "cards"

DEFAULT_IMAGE_DIRECTORY = DEFAULT_RESOURCE_DIRECTORY / "images"

DEFAULT_LOCALE_DIRECTORY = DEFAULT_RESOURCE_DIRECTORY / "locales"

DEFAULT_AUDIO_DIRECTORY = DEFAULT_RESOURCE_DIRECTORY / "audio"

# Supported file types

JSON_EXTENSION = ".json"

YAML_EXTENSION = ".yaml"

YML_EXTENSION = ".yml"

PNG_EXTENSION = ".png"

JPG_EXTENSION = ".jpg"

JPEG_EXTENSION = ".jpeg"

WEBP_EXTENSION = ".webp"

SVG_EXTENSION = ".svg"

OGG_EXTENSION = ".ogg"

WAV_EXTENSION = ".wav"

MP3_EXTENSION = ".mp3"

# Generic resource types

RESOURCE_TYPE_GENERIC = "generic"

RESOURCE_TYPE_CARD = "card"

RESOURCE_TYPE_CONTENT = "content"

RESOURCE_TYPE_IMAGE = "image"

RESOURCE_TYPE_LOCALE = "locale"

RESOURCE_TYPE_AUDIO = "audio"

# Supported extension sets

JSON_EXTENSIONS = frozenset({
    JSON_EXTENSION,
})

YAML_EXTENSIONS = frozenset({
    YAML_EXTENSION,
    YML_EXTENSION,
})

IMAGE_EXTENSIONS = frozenset({
    PNG_EXTENSION,
    JPG_EXTENSION,
    JPEG_EXTENSION,
    WEBP_EXTENSION,
    SVG_EXTENSION,
})

AUDIO_EXTENSIONS = frozenset({
    OGG_EXTENSION,
    WAV_EXTENSION,
    MP3_EXTENSION,
})

TEXT_EXTENSIONS = JSON_EXTENSIONS | YAML_EXTENSIONS
