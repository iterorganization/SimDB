from pathlib import Path

from simdb.uri import URI

from .validator_base import FileValidatorBase


class IdsValidator(FileValidatorBase):
    def configure(self, arguments: dict):
        from imas_validator.validate_options import RuleFilter, ValidateOptions

        # needs to be able to configure from both the [file_validation] server configuration section and the dictionary
        # returned from options()
        list_of_rulesets = []
        list_of_extra_rulesets = []
        list_of_filter_idses = []
        list_of_filter_names = []

        apply_generic = True
        bundled_ruleset = True

        if "rulesets" in arguments:
            rule_files = arguments.get("rulesets")
            if isinstance(rule_files, str):
                # rulesets will be a comma separated string of file names when read from server config
                list_of_rulesets = rule_files.strip('"').split(",")

        if "extra_rule_dirs" in arguments:
            extra_rule_paths = arguments.get("extra_rule_dirs")
            if isinstance(extra_rule_paths, str):
                list_of_extra_rulesets = [
                    Path(ruleset_path)
                    for ruleset_path in extra_rule_paths.strip('"').split(",")
                ]

        ### Define logic for rule_filter
        if "rule_filter_name" in arguments and isinstance(
            arguments.get("rule_filter_name"), str
        ):
            list_of_filter_names = (
                arguments.get("rule_filter_name").strip('"').split(",")
            )

        if "rule_filter_ids" in arguments and isinstance(
            arguments.get("rule_filter_ids"), str
        ):
            list_of_filter_idses = (
                arguments.get("rule_filter_ids").strip('"').split(",")
            )

        # Check if option apply_generic is used and wether it a bool
        if "apply_generic" in arguments and isinstance(
            arguments.get("apply_generic"), bool
        ):
            apply_generic = arguments.get("apply_generic")

        # Check if option bundled_ruleset is used and wether it a bool
        if "bundled_ruleset" in arguments and isinstance(
            arguments.get("bundled_ruleset"), bool
        ):
            bundled_ruleset = arguments.get("bundled_ruleset")

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

    def validate_uri(self, uri: URI, validate_options):
        if uri.scheme != "imas":
            # Skip non IMAS data
            return

        from imas_validator.report.validationReportGenerator import (
            ValidationReportGenerator,
        )
        from imas_validator.validate.validate import validate

        from simdb.validation.validator import ValidationError

        try:
            backend = uri.query.get("backend")
            path = uri.query.get("path")
            validate_uri = f"imas:{backend}?path={path}"

            validate_output = validate(
                imas_uri=URI(validate_uri), validate_options=validate_options
            )

            validate_result = all(
                result.success for result in validate_output.results
            )

            report_generator = ValidationReportGenerator(validate_output)

            if not validate_result:
                raise ValidationError(
                    f"Validation of following URI: [{validate_uri}], failed with following report: \n{report_generator.txt}"
                )
        except Exception as err:
            raise ValidationError(f"validate_uri exception [{err}]")
