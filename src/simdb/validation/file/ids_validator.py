from .validator_base import FileValidatorBase
from ...uri import URI

from pathlib import Path

class IdsValidator(FileValidatorBase):

# # Paths where ids_validator looks for rule sets, comma separated values
# extra_rule_dirs

# # Dictionary of filter criteria comma separated list of key=value elements
# rule_filter =

    def configure(self, arguments: dict):

        from ids_validator.validate_options import ValidateOptions
        from ids_validator.validate_options import RuleFilter

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
                list_of_rulesets = rule_files.split(",")

        if "extra_rule_dirs" in arguments:
            extra_rule_paths = arguments.get("extra_rule_dirs")
            if isinstance(extra_rule_paths, str):
                list_of_extra_rulesets = [
                    Path(ruleset_path)
                    for ruleset_path in extra_rule_paths.split(",")
                ]

        ### Define logic for rule_filter
        if ("rule_filter_name" in arguments and
            isinstance(arguments.get("rule_filter_name"), str)):

            list_of_filter_names = [
                filter_name for filter_name in arguments.get("rule_filter_name").split(",")
            ]

        if ("rule_filter_ids" in arguments and
            isinstance(arguments.get("rule_filter_ids"), str)):

            list_of_filter_idses = [
                filter_ids for filter_ids in arguments.get("rule_filter_ids").split(",")
            ]

        # Check if option apply_generic is used and wether it a bool
        if ("apply_generic" in arguments and
            isinstance(arguments.get("apply_generic"), bool)):
            apply_generic = arguments.get("apply_generic")

        # Check if option bundled_ruleset is used and wether it a bool
        if ("bundled_ruleset" in arguments and
            isinstance(arguments.get("bundled_ruleset"), bool)):
            bundled_ruleset = arguments.get("bundled_ruleset")

        options = ValidateOptions(
            rulesets = list_of_rulesets,
            extra_rule_dirs = list_of_extra_rulesets,
            apply_generic = apply_generic,
            use_pdb = False,
            use_bundled_rulesets = bundled_ruleset,
            rule_filter = RuleFilter(name=list_of_filter_names, ids=list_of_filter_idses),
        )

        print(f"{options =}")
        return options

    def options(self) -> dict:
        # return the rules files as base64 encoded strings
        return {
            "rule_files": [],
        }

    def validate_uri(self, uri: URI, validate_options):
        from ..validator import ValidationError
        from ids_validator.validate.validate import validate
        from ids_validator.report.validationResultGenerator import ValidationResultGenerator

        backend = uri.query.get("backend")
        path = uri.query.get("path").replace("/testdb_summary","")
        validate_uri = f"imas:{backend}?path={path}"

        validate_output = validate(imas_uri=URI(validate_uri), validate_options=validate_options)

        validate_result = all([result.success for result in validate_output.results])

        report_generator = ValidationResultGenerator(validate_output.results)
        print(report_generator.txt)

        if validate_result == False:
            raise ValidationError(f"Validation of following URI: [{validate_uri}], failed")
