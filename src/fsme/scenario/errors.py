# src/fsme/scenario/errors.py

"""
What goes wrong with a scenario file, and how it is said.
"""

from __future__ import annotations


class ScenarioError(ValueError):
    """
    A scenario could not be read, or asks for something that cannot be dealt.

    One exception type rather than a family: everything here is "this file is
    not usable and here is the sentence saying why", and a caller that wanted
    to tell the reasons apart would be re-deciding what the message already
    says.
    """
