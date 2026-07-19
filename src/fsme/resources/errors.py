# src/fsme/resources/errors.py

"""
Exceptions for the resource subsystem.
"""

from __future__ import annotations


class ResourceError(Exception):
    """
    Base resource exception.
    """


class ResourceNotFoundError(ResourceError):
    """
    Raised when a resource cannot be found.
    """


class ResourceAlreadyExistsError(ResourceError):
    """
    Raised when attempting to register an existing resource.
    """


class ResourceLoadError(ResourceError):
    """
    Raised when a resource cannot be loaded.
    """


class ResourceValidationError(ResourceError):
    """
    Raised when a resource is invalid.
    """


class ResourceTypeError(ResourceError):
    """
    Raised when a resource has an unexpected type.
    """
