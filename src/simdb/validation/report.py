"""The outcome of validating a simulation.

The report is stored with the simulation as structured metadata (see
:func:`ValidationReport.to_dict`), so a client can show how many tests passed
or which rule failed without parsing text, and rendered as text for the CLI
and for emails (see :attr:`ValidationReport.text`).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

NODES_SHOWN = 5
"""How many affected nodes a failed rule keeps as examples."""


@dataclass
class TestCounts:
    """How many tests ran and how many of them passed or failed."""

    total: int = 0
    passed: int = 0
    failed: int = 0

    @classmethod
    def of(cls, passed: int, failed: int) -> "TestCounts":
        return cls(total=passed + failed, passed=passed, failed=failed)

    def __add__(self, other: "TestCounts") -> "TestCounts":
        return TestCounts(
            total=self.total + other.total,
            passed=self.passed + other.passed,
            failed=self.failed + other.failed,
        )

    def to_dict(self) -> Dict[str, int]:
        return {"total": self.total, "passed": self.passed, "failed": self.failed}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestCounts":
        return cls(
            total=int(data.get("total", 0)),
            passed=int(data.get("passed", 0)),
            failed=int(data.get("failed", 0)),
        )


def _sum(counts: List[TestCounts]) -> TestCounts:
    total = TestCounts()
    for count in counts:
        total = total + count
    return total


@dataclass
class RuleReport:
    """One validation rule applied to one IDS occurrence.

    A rule is evaluated once per node or time slice it covers, so it has test
    counts of its own; it passes only when every evaluation passed.
    """

    name: str
    tests: TestCounts
    message: str = ""
    """Why the rule failed, from the first failing evaluation."""
    failed_nodes: int = 0
    """How many nodes the failures affect."""
    sample_nodes: List[str] = field(default_factory=list)
    """Up to NODES_SHOWN of the affected nodes."""

    @property
    def passed(self) -> bool:
        return self.tests.failed == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "tests": self.tests.to_dict(),
            "message": self.message,
            "failed_nodes": self.failed_nodes,
            "sample_nodes": list(self.sample_nodes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuleReport":
        return cls(
            name=str(data["name"]),
            tests=TestCounts.from_dict(data.get("tests", {})),
            message=str(data.get("message", "")),
            failed_nodes=int(data.get("failed_nodes", 0)),
            sample_nodes=[str(node) for node in data.get("sample_nodes", [])],
        )


@dataclass
class IdsReport:
    """The rules applied to one IDS occurrence."""

    name: str
    occurrence: int
    rules: List[RuleReport] = field(default_factory=list)

    @property
    def tests(self) -> TestCounts:
        return _sum([rule.tests for rule in self.rules])

    @property
    def passed(self) -> bool:
        return all(rule.passed for rule in self.rules)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "occurrence": self.occurrence,
            "passed": self.passed,
            "tests": self.tests.to_dict(),
            "rules": [rule.to_dict() for rule in self.rules],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IdsReport":
        return cls(
            name=str(data["name"]),
            occurrence=int(data.get("occurrence", 0)),
            rules=[RuleReport.from_dict(rule) for rule in data.get("rules", [])],
        )


@dataclass
class FileReport:
    """The validation of one output file."""

    uri: str
    ids: List[IdsReport] = field(default_factory=list)
    error: Optional[str] = None
    """Why the file could not be validated at all, if it could not."""

    @property
    def tests(self) -> TestCounts:
        return _sum([ids.tests for ids in self.ids])

    @property
    def passed(self) -> bool:
        return self.error is None and all(ids.passed for ids in self.ids)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "passed": self.passed,
            "error": self.error,
            "tests": self.tests.to_dict(),
            "ids": [ids.to_dict() for ids in self.ids],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileReport":
        error = data.get("error")
        return cls(
            uri=str(data["uri"]),
            ids=[IdsReport.from_dict(ids) for ids in data.get("ids", [])],
            error=None if error is None else str(error),
        )

    @property
    def text(self) -> str:
        if self.error is not None:
            return f"File {self.uri} could not be validated:\n{self.error}"
        outcome = "passed" if self.passed else "failed"
        tests = self.tests
        lines = [
            f"File {self.uri} {outcome} validation:",
            f"Number of tests carried out : {tests.total}",
            f"Number of successful tests : {tests.passed}",
            f"Number of failed tests : {tests.failed}",
        ]
        for ids in sorted(self.ids, key=lambda ids: (ids.name, ids.occurrence)):
            status = "PASSED" if ids.passed else "FAILED"
            lines.append("")
            lines.append(f"{status} IDS {ids.name} occurrence {ids.occurrence}")
            for rule in sorted(ids.rules, key=lambda rule: rule.name):
                if rule.passed:
                    lines.append(f"  PASSED {rule.name}")
                    continue
                lines.append(f"  FAILED {rule.name}: {rule.message}")
                if rule.failed_nodes:
                    nodes = ", ".join(rule.sample_nodes)
                    more = rule.failed_nodes - len(rule.sample_nodes)
                    if more > 0:
                        nodes += f" and {more} more"
                    lines.append(f"    {rule.failed_nodes} affected nodes: {nodes}")
        return "\n".join(lines)


@dataclass
class MetadataReport:
    """The validation of the metadata against the schemas."""

    error: Optional[str] = None
    """The schema violations, if there were any."""

    @property
    def passed(self) -> bool:
        return self.error is None

    def to_dict(self) -> Dict[str, Any]:
        return {"passed": self.passed, "error": self.error}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetadataReport":
        error = data.get("error")
        return cls(error=None if error is None else str(error))

    @property
    def text(self) -> str:
        if self.passed:
            return "Metadata passed validation."
        return f"Metadata failed validation:\n{self.error}"


@dataclass
class ValidationReport:
    """The outcome of validating a simulation: its metadata and its files."""

    metadata: MetadataReport = field(default_factory=MetadataReport)
    files: List[FileReport] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.metadata.passed and all(file.passed for file in self.files)

    @property
    def tests(self) -> TestCounts:
        """The file validation tests over every file."""
        return _sum([file.tests for file in self.files])

    def to_dict(self) -> Dict[str, Any]:
        """The report as stored in the simulation metadata.

        Every level carries ``passed`` and ``tests`` so a client can show the
        outcome at the depth it needs without walking the whole tree.
        """
        return {
            "passed": self.passed,
            "tests": self.tests.to_dict(),
            "metadata": self.metadata.to_dict(),
            "files": [file.to_dict() for file in self.files],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationReport":
        return cls(
            metadata=MetadataReport.from_dict(data.get("metadata", {})),
            files=[FileReport.from_dict(file) for file in data.get("files", [])],
        )

    @property
    def text(self) -> str:
        """The report as readable text, for the CLI and for emails."""
        sections = [self.metadata.text]
        sections.extend(file.text for file in self.files)
        return "\n\n".join(sections)
