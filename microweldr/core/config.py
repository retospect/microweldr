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
        """Initialize configuration from TOML file with fallback system.

        Args:
            config_path: Path to configuration file. If None, searches for config files
                        in multiple locations and falls back to defaults if not found.
        """
        self.config_path = self._find_config_file(config_path)
        self._config: Dict[str, Any] = {}
        self.load()

    def _find_config_file(self, config_path: str | Path | None) -> Path | None:
        """Find configuration file using fallback system."""
        if config_path is not None:
            return Path(config_path)

        # Search locations in order of preference
        search_locations = [
            Path.cwd() / "config.toml",  # Current directory
            Path.home() / ".microweldr" / "config.toml",  # User home directory
            Path.home() / "config.toml",  # User home directory (legacy)
            Path(__file__).parent.parent.parent / "config.toml",  # Project root
        ]

        for location in search_locations:
            if location.exists() and location.is_file():
                return location

        # No config file found - will use defaults
        return None

    @classmethod
    def _get_default_config(cls) -> Dict[str, Any]:
        """Get default configuration values."""
        return {
            "printer": {
                "bed_size_x": 250.0,
                "bed_size_y": 220.0,
                "max_z_height": 270.0,
            },
            "nozzle": {
                "outer_diameter": 1.1,
                "inner_diameter": 0.2,
            },
            "temperatures": {
                "bed_temperature": 35,
                "nozzle_temperature": 160,
                "chamber_temperature": 35,
                "use_chamber_heating": False,
                "cooldown_temperature": 50,
            },
            "movement": {
                "move_height": 5.0,
                "travel_speed": 3000,
                "z_speed": 600,
            },
            "normal_welds": {
                "weld_height": 0.020,
                "weld_temperature": 160,
                "weld_time": 0.1,
                "dot_spacing": 0.5,
                "initial_dot_spacing": 3.6,
                "cooling_time_between_passes": 2.0,
            },
            "light_welds": {
                "weld_height": 0.020,
                "weld_temperature": 160,
                "weld_time": 0.3,
                "dot_spacing": 0.5,
                "initial_dot_spacing": 3.6,
                "cooling_time_between_passes": 1.5,
            },
            "output": {
                "gcode_extension": ".gcode",
                "animation_extension": "_animation.svg",
            },
            "sequencing": {
                "skip_base_distance": 5,
            },
            "animation": {
                "time_between_welds": 0.1,
                "pause_time": 3.0,
                "min_animation_duration": 10.0,
            },
        }

    def load(self) -> None:
        """Load configuration from TOML file or use defaults."""
        if self.config_path is None:
            # No config file found, use defaults
            self._config = self._get_default_config()
            return

        try:
            with open(self.config_path, "r") as f:
                loaded_config = toml.load(f)

            # Merge loaded config with defaults to ensure all keys exist
            self._config = self._get_default_config()
            self._merge_config(self._config, loaded_config)

        except FileNotFoundError:
            raise ConfigError(f"Configuration file '{self.config_path}' not found.")
        except toml.TomlDecodeError as e:
            raise ConfigError(f"Invalid TOML configuration: {e}")

    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """Recursively merge override config into base config."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

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
    def light_welds(self) -> Dict[str, Any]:
        """Get light welds configuration."""
        return self.get_section("light_welds")

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
            "light_welds",
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
                "initial_dot_spacing",
                "cooling_time_between_passes",
            ],
            "light_welds": [
                "weld_height",
                "weld_temperature",
                "weld_time",
                "dot_spacing",
                "initial_dot_spacing",
                "cooling_time_between_passes",
            ],
            "animation": ["time_between_welds", "pause_time", "min_animation_duration"],
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
        for weld_type in ["normal_welds", "light_welds"]:
            weld_config = self.get_section(weld_type)
            if weld_config["dot_spacing"] <= 0:
                raise ConfigError(f"{weld_type}.dot_spacing must be positive")
            if weld_config["initial_dot_spacing"] <= 0:
                raise ConfigError(f"{weld_type}.initial_dot_spacing must be positive")
            if weld_config["initial_dot_spacing"] <= weld_config["dot_spacing"]:
                raise ConfigError(
                    f"{weld_type}.initial_dot_spacing must be greater than dot_spacing"
                )
            if weld_config["weld_time"] < 0:
                raise ConfigError(f"{weld_type}.weld_time must be non-negative")
            if weld_config["cooling_time_between_passes"] < 0:
                raise ConfigError(
                    f"{weld_type}.cooling_time_between_passes must be non-negative"
                )

        # Nozzle validations
        nozzle = self.nozzle
        if nozzle["outer_diameter"] <= 0:
            raise ConfigError("nozzle.outer_diameter must be positive")
        if nozzle["inner_diameter"] <= 0:
            raise ConfigError("nozzle.inner_diameter must be positive")
        if nozzle["inner_diameter"] >= nozzle["outer_diameter"]:
            raise ConfigError("nozzle.inner_diameter must be less than outer_diameter")

        # Animation validations
        animation = self.animation
        if animation["time_between_welds"] <= 0:
            raise ConfigError("animation.time_between_welds must be positive")
        if animation["pause_time"] <= 0:
            raise ConfigError("animation.pause_time must be positive")
