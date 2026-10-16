from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from simdb.imas.utils import SimDBUrl

try:
    from imas_validator.validate.validate import validate
    from imas_validator.validate_options import RuleFilter, ValidateOptions

    imas_validator_available = True
except ImportError:
    imas_validator_available = False
else:
    # imas-validator 1.0.0 checks imas.backends.imas_core.imas_interface.has_imas,
    # which imas-python dropped in 2.1. Restore it from the lowlevel interface
    # so the validator does not fail on newer imas-python releases.
    from imas.backends.imas_core import imas_interface as _imas_interface

    if not hasattr(_imas_interface, "has_imas"):
        setattr(  # noqa: B010
            _imas_interface,
            "has_imas",
            getattr(_imas_interface.ll_interface, "_al_version", None) is not None,
        )

from simdb.validation.validator import ValidationError

from .validator_base import FileValidatorBase


def _split_list(value) -> List[str]:
    """Split a comma-separated option into its non-empty, stripped entries.

    An unset option is an empty string, which must not become the single empty
    entry [""]: the validator would then look for a ruleset or rule directory
    named "" and fail.
    """
    return [item.strip() for item in str(value).strip('"').split(",") if item.strip()]


_NODES_SHOWN = 5


@dataclass
class _RuleOutcome:
    passed: int = 0
    failed: int = 0
    message: str = ""
    failed_nodes: int = 0
    sample_nodes: List[str] = field(default_factory=list)


def _text_report(validation_result) -> str:
    """Summarise an IMAS-Validator result collection as readable text.

    Lists every rule that ran on each IDS with its outcome. The validator's own
    text report repeats every affected node, which runs to megabytes for a
    failing profile; this one keeps a handful of nodes per rule so the report
    can be stored with the simulation and mailed to its watchers.
    """
    results = validation_result.results
    failed = sum(1 for result in results if not result.success)
    lines = [
        f"Tested URI : {validation_result.imas_uri}",
        f"Number of tests carried out : {len(results)}",
        f"Number of successful tests : {len(results) - failed}",
        f"Number of failed tests : {failed}",
    ]

    per_ids: Dict[Tuple[str, int], Dict[str, _RuleOutcome]] = {}
    for result in results:
        for ids_key in result.idss:
            outcome = per_ids.setdefault(ids_key, {}).setdefault(
                result.rule.name, _RuleOutcome()
            )
            if result.success:
                outcome.passed += 1
                continue
            outcome.failed += 1
            outcome.message = result.msg
            for node in result.nodes_dict.get(ids_key, ()):
                if not node:
                    continue
                outcome.failed_nodes += 1
                if len(outcome.sample_nodes) < _NODES_SHOWN:
                    outcome.sample_nodes.append(str(node))

    for (ids, occurrence), rules in sorted(per_ids.items()):
        status = "FAILED" if any(rule.failed for rule in rules.values()) else "PASSED"
        lines.append("")
        lines.append(f"{status} IDS {ids} occurrence {occurrence}")
        for name, rule in sorted(rules.items()):
            if not rule.failed:
                lines.append(f"  PASSED {name}")
                continue
            lines.append(f"  FAILED {name}: {rule.message}")
            if rule.failed_nodes:
                nodes = ", ".join(sorted(rule.sample_nodes))
                more = rule.failed_nodes - len(rule.sample_nodes)
                if more > 0:
                    nodes += f" and {more} more"
                lines.append(f"    {rule.failed_nodes} affected nodes: {nodes}")

    return "\n".join(lines) + "\n"


class IdsValidator(FileValidatorBase):
    def configure(self, arguments: dict):
        if not imas_validator_available:
            raise RuntimeError(
                "IMAS-validator not available, please install this optional dependency"
            )
        # needs to be able to configure from both the [file_validation] server
        # configuration section and the dictionary returned from options()
        list_of_rulesets = _split_list(arguments.get("rulesets", ""))
        list_of_extra_rulesets = [
            Path(ruleset_path)
            for ruleset_path in _split_list(arguments.get("extra_rule_dirs", ""))
        ]

        # Define logic for rule_filter
        list_of_filter_names = _split_list(arguments.get("rule_filter_name", ""))
        list_of_filter_idses = _split_list(arguments.get("rule_filter_ids", ""))

        apply_generic = arguments.get("apply_generic", True)
        bundled_ruleset = arguments.get("bundled_ruleset", True)

        options = ValidateOptions(
            rulesets=list_of_rulesets,
            extra_rule_dirs=list_of_extra_rulesets,
            apply_generic=apply_generic,
            use_pdb=False,
            use_bundled_rulesets=bundled_ruleset,
            rule_filter=RuleFilter(name=list_of_filter_names, ids=list_of_filter_idses),
        )

        return options

    def options(self) -> dict:
        # return the rules files as base64 encoded strings
        return {
            "rule_files": [],
        }

    def validate_uri(self, uri: SimDBUrl, validate_options) -> Optional[str]:
        if not imas_validator_available:
            raise RuntimeError(
                "IMAS-validator not available, please install this optional dependency"
            )
        if uri.scheme != "imas":
            # Skip non IMAS data
            return None

        # Validation runs on the server, so always access the data locally: a
        # remote access URI (imas://host/uda?path=...&backend=...) is rewritten
        # to the local form (imas:<backend>?path=...) it was created from.
        qs = dict(uri.query_params())
        backend = qs.get("backend") or uri.path
        path = qs.get("path")
        if not backend or not path:
            raise ValidationError(f"Cannot determine the backend and path of {uri}")
        validate_uri = SimDBUrl.build(scheme="imas", path=backend, query=f"path={path}")

        try:
            validate_output = validate(
                imas_uri=validate_uri.encoded_string(),
                validate_options=validate_options,
            )
        except Exception as err:
            raise ValidationError(f"Failed to validate {validate_uri}: {err}") from err

        # The report lists every rule that ran, whether it passed or failed.
        report = _text_report(validate_output)
        if not all(result.success for result in validate_output.results):
            raise ValidationError(report)
        return report
