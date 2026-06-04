from typing import Optional, Tuple

from .ids_validator import IdsValidator
from .validator_base import FileValidatorBase


def find_file_validator(
    name: str, options: dict
) -> Tuple[Optional[FileValidatorBase], Optional[object]]:
    validators = {
        "ids_validator": IdsValidator,
    }
    if name not in validators:
        return None, None

    validator = validators[name]()
    validate_options = validator.configure(options)
    return validator, validate_options


__all__ = [
    "find_file_validator",
]
