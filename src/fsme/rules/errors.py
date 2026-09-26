"""
Exceptions for the rules subsystem.
"""

from __future__ import annotations

from fsme.util.errors import EngineError


class RuleError(EngineError):
    """
    Base exception for rule failures.
    """


class UnknownRuleError(RuleError):
    """
    Raised when a stack item names a rule procedure the engine does not have.
    """


class RuleRegistrationError(RuleError):
    """
    Raised when a rule procedure is registered twice.
    """
