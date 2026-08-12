# src/fsme/content/manifest.py

"""
Expansion manifests.

A manifest is how a folder of card files says what it is. Without one the
engine would have to infer a set's identity from its directory name, which
would make two people's "custom" folders collide the moment they were shared.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .constants import CONTENT_SCHEMA_VERSION
from .report import IssueCategory, ValidationReport

REQUIRED_FIELDS = ("id", "name", "version")


@dataclass(frozen=True, slots=True)
class Manifest:
    """
    The identity of one content set.
    """

    id: str
    name: str
    version: str

    schema_version: str = CONTENT_SCHEMA_VERSION

    requires: tuple[str, ...] = ()

    description: str = ""
    official: bool = False

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> Manifest:
        """
        Build a manifest from already validated data.
        """
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            version=str(data["version"]),
            schema_version=str(
                data.get("schema_version", CONTENT_SCHEMA_VERSION)
            ),
            requires=tuple(str(item) for item in data.get("requires", ())),
            description=str(data.get("description", "")),
            official=bool(data.get("official", False)),
        )

    def __str__(self) -> str:
        return f"{self.id} {self.version}"


def validate_manifest(
    data: Any,
    *,
    file: str = "",
    report: ValidationReport | None = None,
) -> ValidationReport:
    """
    Check a manifest before anything is loaded on its authority.
    """
    report = report if report is not None else ValidationReport()

    if not isinstance(data, Mapping):
        report.add(
            IssueCategory.SCHEMA,
            f"a manifest must be an object, got {type(data).__name__}",
            file=file,
        )

        return report

    identifier = str(data.get("id", ""))

    for field_name in REQUIRED_FIELDS:
        if not data.get(field_name):
            report.add(
                IssueCategory.SCHEMA,
                f"missing required field '{field_name}'",
                file=file,
                identifier=identifier,
            )

    schema_version = str(data.get("schema_version", CONTENT_SCHEMA_VERSION))

    if schema_version != CONTENT_SCHEMA_VERSION:
        report.add(
            IssueCategory.VERSION,
            f"content schema '{schema_version}' is not supported; "
            f"this engine reads '{CONTENT_SCHEMA_VERSION}'",
            file=file,
            identifier=identifier,
        )

    requires = data.get("requires", ())

    if not isinstance(requires, (list, tuple)):
        report.add(
            IssueCategory.SCHEMA,
            "'requires' must be a list of expansion identifiers",
            file=file,
            identifier=identifier,
        )

    return report
