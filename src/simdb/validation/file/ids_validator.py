from validator_base import FileValidatorBase
from ...uri import URI


class IdsValidator(FileValidatorBase):

    def configure(self, arguments: dict):
        # needs to be able to configure from both the [file_validation] server configuration section and the dictionary
        # returned from options()
        if "rule_files" in arguments:
            rule_files = arguments.get("rule_files")
            if isinstance(rule_files, list):
                # rule_files will be a list of base64 encoded strings when generated from options()
                for rule_file in rule_files:
                    # unpack file
                    ...
            if isinstance(rule_files, str):
                # rule_files will be a comma separated string of file names when read from server config
                rule_file_names = rule_files.split(",")
                for rule_file_name in rule_file_names:
                    # load file
                    ...

    def options(self) -> dict:
        # return the rules files as base64 encoded strings
        return {
            "rule_files": [],
        }

    def validate(self, uri: URI):
        if uri.scheme != "imas":
            return  # ignore non-imas files

        # import ids_validator
        # call ids_validator on the uri
