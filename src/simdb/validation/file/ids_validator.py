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

from simdb.validation.report import (
    NODES_SHOWN,
    FileReport,
    IdsReport,
    RuleReport,
    TestCounts,
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


def _file_report(uri: str, validation_result) -> FileReport:
    """Summarise an IMAS-Validator result collection per IDS and rule.

    The validator evaluates each rule on every node or time slice it covers,
    so a rule has test counts of its own. Only a handful of the affected nodes
    is kept: the validator's own report repeats every one, which runs to
    megabytes for a failing profile.
    """
    rules: Dict[Tuple[str, int], Dict[str, RuleReport]] = {}
    for result in validation_result.results:
        for ids_name, occurrence in result.idss:
            # The validator hands back numpy integers, which JSON cannot store.
            ids_key = (str(ids_name), int(occurrence))
            rule = rules.setdefault(ids_key, {}).setdefault(
                result.rule.name, RuleReport(name=result.rule.name, tests=TestCounts())
            )
            if result.success:
                rule.tests = rule.tests + TestCounts.of(1, 0)
                continue
            rule.tests = rule.tests + TestCounts.of(0, 1)
            if not rule.message:
                rule.message = str(result.msg)
            for node in result.nodes_dict.get((ids_name, occurrence), ()):
                if not node:
                    continue
                rule.failed_nodes += 1
                if len(rule.sample_nodes) < NODES_SHOWN:
                    rule.sample_nodes.append(str(node))

    return FileReport(
        uri=uri,
        ids=[
            IdsReport(name=name, occurrence=occurrence, rules=list(ids_rules.values()))
            for (name, occurrence), ids_rules in sorted(rules.items())
        ],
    )


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

    def validate_uri(self, uri: SimDBUrl, validate_options) -> Optional[FileReport]:
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
        return _file_report(str(uri), validate_output)
