import numpy as np

from simdb.validation.validator import CustomValidator


def test_custom_validator_min_value_max_value():
    schema = {
        "field1": {
            "type": "numpy",
            "coerce": "numpy",
            "min_value": 0.0,
            "max_value": 10.0,
        }
    }
    validator = CustomValidator(schema)

    # Test valid numpy array
    assert validator.validate({"field1": np.array([1.0, 5.0, 9.0])})

    # Test valid dictionary representing a range
    assert validator.validate({"field1": {"min": 1.0, "max": 9.0}})

    # Test numpy array out of bounds (too low)
    assert not validator.validate({"field1": np.array([-1.0, 5.0, 9.0])})

    # Test numpy array out of bounds (too high)
    assert not validator.validate({"field1": np.array([1.0, 5.0, 11.0])})

    # Test dictionary range out of bounds (min too low)
    assert not validator.validate({"field1": {"min": -1.0, "max": 9.0}})

    # Test dictionary range out of bounds (max too high)
    assert not validator.validate({"field1": {"min": 1.0, "max": 11.0}})


def test_custom_validator_comparisons():
    schema = {
        "field_ge": {"type": "numpy", "coerce": "numpy", "ge": 0.0},
        "field_le": {"type": "numpy", "coerce": "numpy", "le": 10.0},
    }
    validator = CustomValidator(schema)

    # Test valid dictionary representing a range
    assert validator.validate(
        {"field_ge": {"min": 0.0, "max": 5.0}, "field_le": {"min": 1.0, "max": 10.0}}
    )

    # Test invalid range for ge (min is -1, which is not >= 0)
    assert not validator.validate(
        {"field_ge": {"min": -1.0, "max": 5.0}, "field_le": {"min": 1.0, "max": 10.0}}
    )

    # Test invalid range for le (max is 11, which is not <= 10)
    assert not validator.validate(
        {"field_ge": {"min": 0.0, "max": 5.0}, "field_le": {"min": 1.0, "max": 11.0}}
    )
