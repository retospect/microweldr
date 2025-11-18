"""Unified configuration system for MicroWeldr - DRY and consistent."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import toml

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when there's an error with configuration loading."""

    pass


class UnifiedConfig:
    """Unified configuration loader for both main config and secrets.

    Standardizes on:
    - microweldr_config.toml for main configuration
    - microweldr_secrets.toml for printer secrets

    Search order (local overrides global):
    1. Current directory
    2. ~/.config/microweldr/
    3. /etc/microweldr/
    """

    def __init__(self):
        """Initialize unified configuration loader."""
        self._main_config: Optional[Dict[str, Any]] = None
        self._secrets_config: Optional[Dict[str, Any]] = None
        self._main_config_path: Optional[Path] = None
        self._secrets_config_path: Optional[Path] = None

    def _find_config_file(
        self, filename: str, legacy_names: list = None
    ) -> Optional[Path]:
        """Find configuration file using standardized search order.

        Args:
            filename: Primary filename to search for
            legacy_names: List of legacy filenames for backward compatibility

        Returns:
            Path to config file or None if not found
        """
        if legacy_names is None:
            legacy_names = []

        # Standardized search locations
        search_locations = [
            Path.cwd(),  # Current directory
            Path.home() / ".config" / "microweldr",  # User config
            Path("/etc/microweldr"),  # System config
        ]

        # Search for primary filename first
        for location in search_locations:
            config_path = location / filename
            if config_path.exists() and config_path.is_file():
                return config_path

        return None

    def _format_config_path_display(self, config_path: Path) -> str:
        """Format config path for display - relative for local, absolute for others."""
        current_dir = Path.cwd()

        # Check if the config file is in the current directory
        try:
            # Resolve both paths to handle symlinks and relative paths
            resolved_config = config_path.resolve()
            resolved_current = current_dir.resolve()

            # If the path is relative to current directory and only one level deep
            relative_path = resolved_config.relative_to(resolved_current)
            if len(relative_path.parts) == 1:  # File is directly in current directory
                return f"./{relative_path}"
        except ValueError:
            # Path is not relative to current directory
            pass

        # For all other cases, use absolute path
        return str(config_path.resolve())

    def get_main_config(self) -> Dict[str, Any]:
        """Get main configuration (microweldr_config.toml)."""
        if self._main_config is not None:
            return self._main_config

        # Find main config file - NO LEGACY SUPPORT
        config_path = self._find_config_file("microweldr_config.toml")

        if config_path is None:
            # Use default configuration
            self._main_config = self._get_default_main_config()
            print(f"Using default main configuration (no microweldr_config.toml found)")
            return self._main_config

        try:
            with open(config_path, "r") as f:
                loaded_config = toml.load(f)

            # Merge with defaults
            self._main_config = self._get_default_main_config()
            self._merge_config(self._main_config, loaded_config)
            self._main_config_path = config_path

            display_path = self._format_config_path_display(config_path)
            print(f"✓ Configuration loaded from {display_path}")
            return self._main_config

        except Exception as e:
            raise ConfigurationError(
                f"Failed to load main config from {config_path}: {e}"
            )

    def get_secrets_config(self) -> Dict[str, Any]:
        """Get secrets configuration (microweldr_secrets.toml)."""
        if self._secrets_config is not None:
            return self._secrets_config

        # Find secrets config file
        config_path = self._find_config_file(
            "microweldr_secrets.toml", legacy_names=["secrets.toml"]
        )

        if config_path is None:
            raise ConfigurationError(
                "No secrets configuration found. Please create one of:\n"
                "  - ./microweldr_secrets.toml\n"
                "  - ~/.config/microweldr/microweldr_secrets.toml\n"
                "  - /etc/microweldr/microweldr_secrets.toml\n"
                "\nRun 'microweldr config init' to create a template."
            )

        try:
            with open(config_path, "r") as f:
                self._secrets_config = toml.load(f)

            self._secrets_config_path = config_path
            display_path = self._format_config_path_display(config_path)
            print(f"✓ Secrets loaded from {display_path}")
            return self._secrets_config

        except Exception as e:
            raise ConfigurationError(
                f"Failed to load secrets config from {config_path}: {e}"
            )

    def get_prusalink_config(self) -> Dict[str, Any]:
        """Get PrusaLink configuration from secrets."""
        secrets = self.get_secrets_config()

        if "prusalink" not in secrets:
            raise ConfigurationError(
                "No 'prusalink' section found in secrets configuration. "
                "Please check your microweldr_secrets.toml file."
            )

        return secrets["prusalink"]

    def _get_default_main_config(self) -> Dict[str, Any]:
        """Get default main configuration."""
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
                "cooldown_temperature": 0,
                "enable_cooldown": False,
            },
            "movement": {
                "move_height": 5.0,
                "low_travel_height": 1.2,
                "travel_speed": 3000,
                "z_speed": 600,
                "weld_height": 0.02,
                "weld_move_height": 2.0,
                "weld_compression_offset": 0.0,
            },
            "normal_welds": {
                "weld_height": 0.01,
                "weld_temperature": 160,
                "weld_time": 0.2,
                "dot_spacing": 0.5,
            },
            "frangible_welds": {
                "weld_height": 0.6,
                "weld_temperature": 160,
                "weld_time": 0.2,
                "dot_spacing": 0.5,
            },
            "output": {
                "gcode_extension": ".gcode",
                "animation_extension": "_animation.svg",
            },
            "sequencing": {
                "skip_base_distance": 5,
                "passes": 4,
            },
            # Animation parameters removed - not currently implemented
        }

    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """Recursively merge override config into base config."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def get_main_config_path(self) -> Optional[Path]:
        """Get path to main config file."""
        if self._main_config is None:
            self.get_main_config()
        return self._main_config_path

    def get_secrets_config_path(self) -> Optional[Path]:
        """Get path to secrets config file."""
        if self._secrets_config is None:
            self.get_secrets_config()
        return self._secrets_config_path


# Global instance for consistent access
_unified_config: Optional[UnifiedConfig] = None


def get_unified_config() -> UnifiedConfig:
    """Get global unified configuration instance."""
    global _unified_config
    if _unified_config is None:
        _unified_config = UnifiedConfig()
    return _unified_config


def reset_unified_config():
    """Reset global configuration (for testing)."""
    global _unified_config
    _unified_config = None


# Convenience functions for backward compatibility
def get_main_config() -> Dict[str, Any]:
    """Get main configuration."""
    return get_unified_config().get_main_config()


def get_secrets_config() -> Dict[str, Any]:
    """Get secrets configuration."""
    return get_unified_config().get_secrets_config()


def get_prusalink_config() -> Dict[str, Any]:
    """Get PrusaLink configuration."""
    return get_unified_config().get_prusalink_config()
