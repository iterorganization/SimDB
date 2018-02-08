import yaml
import sys
import os


class ValidationError(Exception):
    pass


class Manifest:

    def __init__(self):
        self.data = None

    def load(self, file_name):
        with open(file_name) as file:
            self.data = yaml.load(file)

    def validate(self):
        # * Check diff files exist
        # * Check contents of diff file - do they match the git diff provided
        pass

    @staticmethod
    def create(file_name):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        with open(dir_path + "/template.yaml") as file:
            if file_name is None or file_name == "-":
                yaml.dump(yaml.load(file), sys.stdout, default_flow_style=False)
            else:
                if os.path.exists(file_name):
                    raise Exception("file already exists")
                with open(file_name, "w") as out_file:
                    yaml.dump(yaml.load(file), out_file, default_flow_style=False)
