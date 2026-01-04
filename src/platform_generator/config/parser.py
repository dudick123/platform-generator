"""YAML configuration parser."""

from pathlib import Path
from typing import Any, Dict

from pydantic import ValidationError
from ruamel.yaml import YAML

from .models import PlatformConfig


class ConfigParseError(Exception):
    """Exception raised when configuration parsing fails."""

    pass


class ConfigParser:
    """Parser for platform.yaml configuration files."""

    def __init__(self) -> None:
        """Initialize the parser."""
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.default_flow_style = False

    def load_file(self, path: Path) -> PlatformConfig:
        """
        Load and parse a platform.yaml configuration file.

        Args:
            path: Path to the platform.yaml file

        Returns:
            Parsed platform configuration

        Raises:
            ConfigParseError: If the file cannot be parsed or validated
        """
        try:
            with open(path, "r") as f:
                data = self.yaml.load(f)
        except FileNotFoundError:
            raise ConfigParseError(f"Configuration file not found: {path}")
        except Exception as e:
            raise ConfigParseError(f"Failed to read configuration file: {e}")

        return self.parse_dict(data, path)

    def parse_dict(self, data: Dict[str, Any], source: Path | None = None) -> PlatformConfig:
        """
        Parse a configuration dictionary into a PlatformConfig model.

        Args:
            data: Configuration dictionary
            source: Optional source file path for error reporting

        Returns:
            Parsed platform configuration

        Raises:
            ConfigParseError: If validation fails
        """
        try:
            config = PlatformConfig(**data)
            return config
        except ValidationError as e:
            error_msg = self._format_validation_error(e, source)
            raise ConfigParseError(error_msg)
        except Exception as e:
            raise ConfigParseError(f"Failed to parse configuration: {e}")

    def _format_validation_error(self, error: ValidationError, source: Path | None) -> str:
        """Format a Pydantic validation error into a user-friendly message."""
        lines = []
        if source:
            lines.append(f"Validation errors in {source}:")
        else:
            lines.append("Validation errors:")

        for err in error.errors():
            location = " -> ".join(str(loc) for loc in err["loc"])
            msg = err["msg"]
            error_type = err["type"]

            lines.append(f"  - {location}: {msg} (type={error_type})")

        return "\n".join(lines)

    def validate_file(self, path: Path) -> tuple[bool, str]:
        """
        Validate a configuration file without fully parsing it.

        Args:
            path: Path to the platform.yaml file

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            self.load_file(path)
            return True, ""
        except ConfigParseError as e:
            return False, str(e)
