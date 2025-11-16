"""Configuration management for the SVG welder."""

from pathlib import Path
from typing import Any, Dict

import toml


class ConfigError(Exception):
    """Raised when there's an error with configuration."""

    pass


class Config:
    """Configuration manager for the SVG welder."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        """Initialize configuration using unified configuration system.

        Args:
            config_path: Legacy parameter for backward compatibility (ignored)
        """
        if config_path is not None:
            import warnings

            warnings.warn(
                "Config path parameter is deprecated. Using unified configuration system.",
                DeprecationWarning,
                stacklevel=2,
            )

        from .unified_config import get_main_config

        self._config = get_main_config()

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        try:
            return self._config[section][key]
        except KeyError:
            if default is not None:
                return default
            raise ConfigError(f"Configuration key '{section}.{key}' not found")

    def get_section(self, section: str) -> Dict[str, Any]:
        """Get an entire configuration section."""
        try:
            return self._config[section]
        except KeyError:
            raise ConfigError(f"Configuration section '{section}' not found")

    @property
    def printer(self) -> Dict[str, Any]:
        """Get printer configuration."""
        return self.get_section("printer")

    @property
    def temperatures(self) -> Dict[str, Any]:
        """Get temperature configuration."""
        return self.get_section("temperatures")

    @property
    def movement(self) -> Dict[str, Any]:
        """Get movement configuration."""
        return self.get_section("movement")

    @property
    def normal_welds(self) -> Dict[str, Any]:
        """Get normal welds configuration."""
        return self.get_section("normal_welds")

    @property
    def frangible_welds(self) -> Dict[str, Any]:
        """Get frangible welds configuration."""
        return self.get_section("frangible_welds")

    @property
    def output(self) -> Dict[str, Any]:
        """Get output configuration."""
        return self.get_section("output")

    @property
    def animation(self) -> Dict[str, Any]:
        """Get animation configuration."""
        return self.get_section("animation")

    @property
    def nozzle(self) -> Dict[str, Any]:
        """Get nozzle configuration."""
        return self.get_section("nozzle")

    @property
    def sequencing(self) -> Dict[str, Any]:
        """Get sequencing configuration."""
        try:
            return self.get_section("sequencing")
        except ConfigError:
            # Return default values if section doesn't exist
            return {"skip_base_distance": 5}

    @property
    def config(self) -> Dict[str, Any]:
        """Get the full configuration dictionary."""
        return self._config

    def validate(self) -> None:
        """Validate configuration completeness and correctness."""
        required_sections = [
            "printer",
            "nozzle",
            "temperatures",
            "movement",
            "normal_welds",
            "frangible_welds",
            "output",
            "animation",
        ]
        # Note: sequencing section is optional with defaults

        for section in required_sections:
            if section not in self._config:
                raise ConfigError(f"Missing required configuration section: {section}")

        # Validate specific required keys
        required_keys = {
            "nozzle": ["outer_diameter", "inner_diameter"],
            "temperatures": [
                "bed_temperature",
                "nozzle_temperature",
                "cooldown_temperature",
            ],
            "movement": ["move_height", "travel_speed", "z_speed"],
            "normal_welds": [
                "weld_height",
                "weld_temperature",
                "weld_time",
                "dot_spacing",
            ],
            "frangible_welds": [
                "weld_height",
                "weld_temperature",
                "weld_time",
                "dot_spacing",
            ],
        }

        for section, keys in required_keys.items():
            section_config = self.get_section(section)
            for key in keys:
                if key not in section_config:
                    raise ConfigError(
                        f"Missing required key '{key}' in section '{section}'"
                    )

        # Validate value ranges
        self._validate_ranges()

    def _validate_ranges(self) -> None:
        """Validate configuration value ranges."""
        # Temperature validations
        temps = self.temperatures
        if temps["bed_temperature"] < 0 or temps["bed_temperature"] > 150:
            raise ConfigError("bed_temperature must be between 0 and 150°C")

        if temps["nozzle_temperature"] < 0 or temps["nozzle_temperature"] > 300:
            raise ConfigError("nozzle_temperature must be between 0 and 300°C")

        # Movement validations
        movement = self.movement
        if movement["move_height"] < 0:
            raise ConfigError("move_height must be positive")

        # Weld validations
        for weld_type in ["normal_welds", "frangible_welds"]:
            weld_config = self.get_section(weld_type)
            if weld_config["dot_spacing"] <= 0:
                raise ConfigError(f"{weld_type}.dot_spacing must be positive")
            if weld_config["weld_time"] < 0:
                raise ConfigError(f"{weld_type}.weld_time must be non-negative")

        # Nozzle validations
        nozzle = self.nozzle
        if nozzle["outer_diameter"] <= 0:
            raise ConfigError("nozzle.outer_diameter must be positive")
        if nozzle["inner_diameter"] <= 0:
            raise ConfigError("nozzle.inner_diameter must be positive")
        if nozzle["inner_diameter"] >= nozzle["outer_diameter"]:
            raise ConfigError("nozzle.inner_diameter must be less than outer_diameter")

        # Animation validations removed - parameters not currently used
