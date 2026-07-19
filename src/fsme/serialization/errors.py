# src/fsme/serialization/errors.py

"""
Serialization-related exceptions for Four Souls Multiverse Engine.
"""

from __future__ import annotations


class SerializationError(Exception):
    """
    Base exception for the serialization subsystem.
    """


class SerializeError(SerializationError):
    """
    Raised when serialization fails.
    """


class DeserializeError(SerializationError):
    """
    Raised when deserialization fails.
    """


class InvalidDataError(SerializationError):
    """
    Raised when serialized data is invalid.
    """


class InvalidFormatError(SerializationError):
    """
    Raised when an unsupported serialization format is encountered.
    """


class FileReadError(SerializationError):
    """
    Raised when a file cannot be read.
    """


class FileWriteError(SerializationError):
    """
    Raised when a file cannot be written.
    """