# src/fsme/validation/errors.py

"""
Validation-related exceptions for Four Souls Multiverse Engine.
"""

from __future__ import annotations


class ValidationError(Exception):
    """
    Base exception for the validation subsystem.
    """


class ValidatorError(ValidationError):
    """
    Raised when a validator cannot perform validation.
    """


class ValidationFailedError(ValidationError):
    """
    Raised when validation fails.
    """


class InvalidSchemaError(ValidationError):
    """
    Raised when a validation schema is invalid.
    """


class MissingFieldError(ValidationError):
    """
    Raised when a required field is missing.
    """


class InvalidFieldError(ValidationError):
    """
    Raised when a field contains an invalid value.
    """


class RuleRegistrationError(ValidationError):
    """
    Raised when a validation rule cannot be registered.
    """