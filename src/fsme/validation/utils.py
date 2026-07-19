# src/fsme/validation/utils.py

"""
Utility helpers for the validation subsystem.
"""

from __future__ import annotations

from .validator import Validator


def is_validator(value: object) -> bool:
    """
    Return True if the value is a Validator.
    """
    return isinstance(value, Validator)


def ensure_validator(value: object) -> Validator:
    """
    Ensure that the provided value is a Validator.
    """
    if not isinstance(value, Validator):
        raise TypeError(
            f"Expected Validator, got {type(value).__name__}."
        )

    return value


def validator_name(validator: Validator) -> str:
    """
    Return the validator class name.
    """
    return validator.__class__.__name__


def rule_count(validator: Validator) -> int:
    """
    Return the number of registered validation rules.
    """
    return len(validator.rules)