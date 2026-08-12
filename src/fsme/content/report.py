# src/fsme/content/report.py

"""
Validation reporting.

CONTENT_PIPELINE.md section 10 asks for the file, the identifier, the location,
a category and a readable explanation, and for as many problems as possible to
be found in one pass. Someone fixing an expansion should get the whole list,
not the first line that failed.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from .errors import InvalidContentError


class IssueCategory(StrEnum):
    """
    What kind of problem was found.
    """

    FORMAT = "format"
    """The file could not be read or parsed."""

    SCHEMA = "schema"
    """A field is missing, or has the wrong type."""

    SEMANTIC = "semantic"
    """The card names something the engine does not implement."""

    REFERENCE = "reference"
    """The card or manifest points at something that is not there."""

    DUPLICATE = "duplicate"
    """An identifier is used twice."""

    VERSION = "version"
    """The content was written for a different schema."""


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """
    One problem, described well enough to fix without guessing.
    """

    category: IssueCategory
    message: str

    file: str = ""
    identifier: str = ""
    location: str = ""

    def __str__(self) -> str:
        where = " ".join(
            part
            for part in (self.file, self.identifier, self.location)
            if part
        )

        return f"[{self.category}] {where}: {self.message}" if where else (
            f"[{self.category}] {self.message}"
        )


@dataclass(slots=True)
class ValidationReport:
    """
    Everything wrong with a batch of content.
    """

    issues: list[ValidationIssue] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.issues)

    def __iter__(self) -> Iterator[ValidationIssue]:
        return iter(self.issues)

    def __bool__(self) -> bool:
        return self.ok

    @property
    def ok(self) -> bool:
        """
        True when nothing is wrong.
        """
        return not self.issues

    def add(
        self,
        category: IssueCategory,
        message: str,
        *,
        file: str = "",
        identifier: str = "",
        location: str = "",
    ) -> ValidationIssue:
        """
        Record a problem.
        """
        issue = ValidationIssue(
            category=category,
            message=message,
            file=file,
            identifier=identifier,
            location=location,
        )

        self.issues.append(issue)

        return issue

    def extend(self, issues: Iterable[ValidationIssue]) -> None:
        self.issues.extend(issues)

    def of_category(self, category: IssueCategory) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.category is category)

    def raise_if_failed(self, what: str = "content") -> None:
        """
        Turn a failed report into one exception listing every problem.
        """
        if self.ok:
            return

        listing = "\n  ".join(str(issue) for issue in self.issues)

        raise InvalidContentError(f"invalid {what}:\n  {listing}")

    def __str__(self) -> str:
        if self.ok:
            return "content is valid"

        return f"{len(self.issues)} problem(s):\n" + "\n".join(
            f"  {issue}" for issue in self.issues
        )
