# src/fsme/validation/__init__.py

"""
Validation subsystem exports.
"""

from .constants import (
    DEFAULT_ALLOW_WARNINGS,
    DEFAULT_ENCODING,
    DEFAULT_MAX_ERRORS,
    DEFAULT_MAX_WARNINGS,
    DEFAULT_SCHEMA_VERSION,
    DEFAULT_STOP_ON_ERROR,
    DEFAULT_STRICT_MODE,
    DEFAULT_VALIDATION_NAMESPACE,
    DEFAULT_VALIDATION_PROFILE,
    MAX_ERROR_MESSAGE_LENGTH,
    MAX_RULE_NAME_LENGTH,
)
from .context import ValidationContext
from .dispatcher import ValidationDispatcher
from .errors import (
    InvalidFieldError,
    InvalidSchemaError,
    MissingFieldError,
    RuleRegistrationError,
    ValidationError,
    ValidationFailedError,
    ValidatorError,
)
from .handler import ValidationHandler
from .resolver import ValidationResolver
from .result import ValidationResult
from .utils import (
    ensure_validator,
    is_validator,
    rule_count,
    validator_name,
)
from .validator import ValidationRule, Validator

__all__ = [
    "Validator",
    "ValidationRule",
    "ValidationContext",
    "ValidationHandler",
    "ValidationResolver",
    "ValidationDispatcher",
    "ValidationResult",
    "ValidationError",
    "ValidatorError",
    "ValidationFailedError",
    "InvalidSchemaError",
    "MissingFieldError",
    "InvalidFieldError",
    "RuleRegistrationError",
    "DEFAULT_MAX_ERRORS",
    "DEFAULT_MAX_WARNINGS",
    "DEFAULT_STRICT_MODE",
    "DEFAULT_STOP_ON_ERROR",
    "DEFAULT_ALLOW_WARNINGS",
    "DEFAULT_ENCODING",
    "DEFAULT_SCHEMA_VERSION",
    "DEFAULT_VALIDATION_NAMESPACE",
    "DEFAULT_VALIDATION_PROFILE",
    "MAX_RULE_NAME_LENGTH",
    "MAX_ERROR_MESSAGE_LENGTH",
    "is_validator",
    "ensure_validator",
    "validator_name",
    "rule_count",
]