from pathlib import Path
from typing import Optional

from simdb.imas.utils import SimDBUrl

try:
    from imas_validator.report.validationReportGenerator import (
        ValidationReportGenerator,
    )
    from imas_validator.validate.validate import validate
    from imas_validator.validate_options import RuleFilter, ValidateOptions

    imas_validator_available = True
except ImportError:
    imas_validator_available = False

from simdb.validation.validator import ValidationError

from .validator_base import FileValidatorBase


class IdsValidator(FileValidatorBase):
    def configure(self, arguments: dict):
        if not imas_validator_available:
            raise RuntimeError(
                "IMAS-validator not available, please install this optional dependency"
            )
        # needs to be able to configure from both the [file_validation] server
        # configuration section and the dictionary returned from options()
        list_of_rulesets = []
        list_of_extra_rulesets = []
        list_of_filter_idses = []
        list_of_filter_names = []

        apply_generic = True
        bundled_ruleset = True

        list_of_rulesets = arguments.get("rulesets", "").strip('"').split(",")

        list_of_extra_rulesets = [
            Path(ruleset_path)
            for ruleset_path in arguments.get("extra_rule_dirs", "")
            .strip('"')
            .split(",")
        ]

        # Define logic for rule_filter
        list_of_filter_names = (
            arguments.get("rule_filter_name", "").strip('"').split(",")
        )

        list_of_filter_idses = (
            arguments.get("rule_filter_ids", "").strip('"').split(",")
        )

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
        report = ValidationReportGenerator(validate_output).txt
        if not all(result.success for result in validate_output.results):
            raise ValidationError(report)
        return report
