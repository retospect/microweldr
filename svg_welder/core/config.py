"""Configuration management for the SVG welder."""

import sys
from pathlib import Path
from typing import Any, Dict

import toml


class ConfigError(Exception):
    """Raised when there's an error with configuration."""
    pass


class Config:
    """Configuration manager for the SVG welder."""
    
    def __init__(self, config_path: str | Path) -> None:
        """Initialize configuration from TOML file."""
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load configuration from TOML file."""
        try:
            with open(self.config_path, 'r') as f:
                self._config = toml.load(f)
        except FileNotFoundError:
            raise ConfigError(f"Configuration file '{self.config_path}' not found.")
        except toml.TomlDecodeError as e:
            raise ConfigError(f"Invalid TOML configuration: {e}")

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
        return self.get_section('printer')

    @property
    def temperatures(self) -> Dict[str, Any]:
        """Get temperature configuration."""
        return self.get_section('temperatures')

    @property
    def movement(self) -> Dict[str, Any]:
        """Get movement configuration."""
        return self.get_section('movement')

    @property
    def normal_welds(self) -> Dict[str, Any]:
        """Get normal welds configuration."""
        return self.get_section('normal_welds')

    @property
    def light_welds(self) -> Dict[str, Any]:
        """Get light welds configuration."""
        return self.get_section('light_welds')

    @property
    def output(self) -> Dict[str, Any]:
        """Get output configuration."""
        return self.get_section('output')

    @property
    def animation(self) -> Dict[str, Any]:
        """Get animation configuration."""
        return self.get_section('animation')

    @property
    def nozzle(self) -> Dict[str, Any]:
        """Get nozzle configuration."""
        return self.get_section('nozzle')

    def validate(self) -> None:
        """Validate configuration completeness and correctness."""
        required_sections = [
            'printer', 'nozzle', 'temperatures', 'movement', 
            'normal_welds', 'light_welds', 'output', 'animation'
        ]
        
        for section in required_sections:
            if section not in self._config:
                raise ConfigError(f"Missing required configuration section: {section}")

        # Validate specific required keys
        required_keys = {
            'nozzle': ['outer_diameter', 'inner_diameter'],
            'temperatures': ['bed_temperature', 'nozzle_temperature', 'cooldown_temperature'],
            'movement': ['move_height', 'travel_speed', 'z_speed'],
            'normal_welds': ['weld_height', 'weld_temperature', 'spot_dwell_time', 'dot_spacing'],
            'light_welds': ['weld_height', 'weld_temperature', 'spot_dwell_time', 'dot_spacing'],
            'animation': ['time_between_welds', 'pause_time', 'min_animation_duration']
        }

        for section, keys in required_keys.items():
            section_config = self.get_section(section)
            for key in keys:
                if key not in section_config:
                    raise ConfigError(f"Missing required key '{key}' in section '{section}'")

        # Validate value ranges
        self._validate_ranges()

    def _validate_ranges(self) -> None:
        """Validate configuration value ranges."""
        # Temperature validations
        temps = self.temperatures
        if temps['bed_temperature'] < 0 or temps['bed_temperature'] > 150:
            raise ConfigError("bed_temperature must be between 0 and 150°C")
        
        if temps['nozzle_temperature'] < 0 or temps['nozzle_temperature'] > 300:
            raise ConfigError("nozzle_temperature must be between 0 and 300°C")

        # Movement validations
        movement = self.movement
        if movement['move_height'] < 0:
            raise ConfigError("move_height must be positive")

        # Weld validations
        for weld_type in ['normal_welds', 'light_welds']:
            weld_config = self.get_section(weld_type)
            if weld_config['dot_spacing'] <= 0:
                raise ConfigError(f"{weld_type}.dot_spacing must be positive")
            if weld_config['spot_dwell_time'] < 0:
                raise ConfigError(f"{weld_type}.spot_dwell_time must be non-negative")

        # Nozzle validations
        nozzle = self.nozzle
        if nozzle['outer_diameter'] <= 0:
            raise ConfigError("nozzle.outer_diameter must be positive")
        if nozzle['inner_diameter'] <= 0:
            raise ConfigError("nozzle.inner_diameter must be positive")
        if nozzle['inner_diameter'] >= nozzle['outer_diameter']:
            raise ConfigError("nozzle.inner_diameter must be less than outer_diameter")

        # Animation validations
        animation = self.animation
        if animation['time_between_welds'] <= 0:
            raise ConfigError("animation.time_between_welds must be positive")
        if animation['pause_time'] <= 0:
            raise ConfigError("animation.pause_time must be positive")
