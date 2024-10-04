from abc import ABC, abstractmethod
from ...uri import URI

class FileValidatorBase(ABC):
    """
    Abstract base class for validating a simulation output file.
    """

    @abstractmethod
    def configure(self, arguments: dict):
        """
        Configure the validator with the given arguments.

        Needs to be able to configure the validator from both the options found in the [file_validation] section of the
        server configuration file, and from the dictionary returned from the options() method.
        """

    @abstractmethod
    def options(self) -> dict:
        """
        Return a dictionary of options required to configure the validator into the same state.
        """

    @abstractmethod
    def validate_uri(self, uri: URI, validate_options):
        """
        Validate the given simulation output file.
        """
