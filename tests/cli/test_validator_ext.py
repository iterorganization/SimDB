from unittest import mock

import pytest

from simdb.validation.validator import CustomValidator, Validator


class TestCustomValidatorExt:
    @pytest.fixture
    def validator_instance(self):
        return Validator.__new__(Validator)

    def test_validator_ext_when_none(self, validator_instance):
        config = mock.MagicMock()
        config.get_option.return_value = None

        result = validator_instance._custom_validation_ext(config)

        assert result is CustomValidator

        config.get_option.assert_called_once_with(
            "validation.custom_validator", default=None
        )

    def test_raises_type_error_for_non_string(self, validator_instance):
        config = mock.MagicMock()
        config.get_option.return_value = 12345

        with pytest.raises(TypeError) as exc_info:
            validator_instance._custom_validation_ext(config)

        assert "Expected 'custom_validator config value' to be a string" in str(
            exc_info.value
        )

        config.get_option.assert_called_once_with(
            "validation.custom_validator", default=None
        )

    def test_raises_value_error_for_missing_dot(self, validator_instance):
        config = mock.MagicMock()
        config.get_option.return_value = "InvalidPathWithoutDot"

        with pytest.raises(ValueError) as exc_info:
            validator_instance._custom_validation_ext(config)

        assert "Expected format: 'package.module.ClassName'" in str(
            exc_info.value
        )

        config.get_option.assert_called_once_with(
            "validation.custom_validator", default=None
        )

    @mock.patch("simdb.validation.validator.import_module")
    def test_raises_import_error_on_module_not_found(
        self, mock_import_module, validator_instance
    ):
        config = mock.MagicMock()
        config.get_option.return_value = "non_existent_pkg.module.MyValidator"
        mock_import_module.side_effect = ModuleNotFoundError(
            "No module named 'non_existent_pkg'"
        )

        with pytest.raises(ImportError):
            validator_instance._custom_validation_ext(config)

        mock_import_module.assert_called_once_with("non_existent_pkg.module")

    @mock.patch("simdb.validation.validator.import_module")
    def test_returns_custom_class_successfully(
        self, mock_import_module, validator_instance
    ):
        config = mock.MagicMock()
        config.get_option.return_value = "mypackage.validator.MyValidator"

        mock_module = mock.MagicMock()
        mock_validator_class = mock.MagicMock()

        mock_module.MyValidator = mock_validator_class

        mock_import_module.return_value = mock_module

        result = validator_instance._custom_validation_ext(config)

        assert result is mock_validator_class
        mock_import_module.assert_called_once_with("mypackage.validator")

    @mock.patch("simdb.validation.validator.import_module")
    def test_raise_attribute_error_when_class_missing(
        self, mock_import_module, validator_instance
    ):
        config = mock.MagicMock()
        config.get_option.return_value = "mypackage.validator.MyValidator"

        mock_module = mock.MagicMock(spec=[])
        mock_import_module.return_value = mock_module

        with pytest.raises(
            AttributeError,
            match="does not have class or attribute 'MyValidator'",
        ):
            validator_instance._custom_validation_ext(config)
            mock_import_module.assert_called_once_with("mypackage.validator")
