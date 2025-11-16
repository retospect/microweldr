"""Hierarchical secrets configuration management using python-configuration."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import toml


class SecretsConfig:
    """Hierarchical secrets configuration loader for MicroWeldr.

    Searches for 'microweldr_secrets.toml' files in a hierarchy from the current
    directory up to the root, merging configurations with more local settings
    overriding global ones.

    Search order (local overrides global):
    1. ./microweldr_secrets.toml (current directory)
    2. ../microweldr_secrets.toml (parent directory)
    3. ../../microweldr_secrets.toml (grandparent directory)
    4. ... (continues up to root)
    5. ~/.config/microweldr/microweldr_secrets.toml (user config)
    6. /etc/microweldr/microweldr_secrets.toml (system config)

    Also supports legacy 'secrets.toml' in current directory for backward compatibility.
    """

    def __init__(self, config_name: str = "microweldr_secrets.toml"):
        """Initialize the secrets configuration loader.

        Args:
            config_name: Name of the configuration file to search for
        """
        self.config_name = config_name
        self.legacy_name = "secrets.toml"
        self._config: Optional[Dict[str, Any]] = None
        self._config_sources: List[Path] = []

    def load(self) -> Dict[str, Any]:
        """Load and merge configuration files from the hierarchy.

        Returns:
            Merged configuration dictionary

        Raises:
            FileNotFoundError: If no configuration files are found
        """
        if self._config is not None:
            return self._config

        config_files = self._find_config_files()

        if not config_files:
            raise FileNotFoundError(
                f"No configuration files found. Please create one of:\n"
                f"  - ./{self.config_name}\n"
                f"  - ./{self.legacy_name} (legacy)\n"
                f"  - ~/.config/microweldr/{self.config_name}\n"
                f"  - /etc/microweldr/{self.config_name}\n"
                f"\nUse the template from {self.legacy_name}.template"
            )

        # Load configuration with hierarchical merging
        # Start with empty config and merge files from global to local
        merged_config = {}

        for (
            config_file
        ) in config_files:  # Files are already ordered from global to local
            try:
                with open(config_file, "r") as f:
                    file_config = toml.load(f)
                # Merge this file's config into the accumulated config
                for key, value in file_config.items():
                    merged_config[key] = value
                self._config_sources.append(config_file)
                print(f"Loaded config from: {config_file}")
            except Exception as e:
                print(f"Warning: Failed to load {config_file}: {e}")

        # Store the merged configuration data
        self._config = merged_config

        return self._config

    def _find_config_files(self) -> List[Path]:
        """Find all configuration files in the hierarchy.

        Returns:
            List of configuration file paths, ordered from global to local
        """
        config_files = []

        # 1. System-wide configuration
        system_config = Path("/etc/microweldr") / self.config_name
        if system_config.exists():
            config_files.append(system_config)

        # 2. User configuration
        user_config = Path.home() / ".config" / "microweldr" / self.config_name
        if user_config.exists():
            config_files.append(user_config)

        # 3. Traverse directory hierarchy from root to current directory
        current_path = Path.cwd().resolve()
        hierarchy_configs = []

        # Walk up the directory tree
        for parent in [current_path] + list(current_path.parents):
            config_file = parent / self.config_name
            if config_file.exists():
                hierarchy_configs.append(config_file)

        # Add hierarchy configs in reverse order (root to current)
        config_files.extend(reversed(hierarchy_configs))

        return config_files

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.

        Args:
            key: Configuration key (supports dot notation, e.g., 'prusalink.host')
            default: Default value if key is not found

        Returns:
            Configuration value or default
        """
        if self._config is None:
            self.load()

        try:
            return self._config.get(key, default)
        except Exception:
            return default

    def get_prusalink_config(self) -> Dict[str, Any]:
        """Get PrusaLink configuration section.

        Returns:
            Dictionary containing PrusaLink configuration

        Raises:
            KeyError: If prusalink section is not found
        """
        if self._config is None:
            self.load()

        if "prusalink" not in self._config:
            raise KeyError(
                "No 'prusalink' configuration section found. "
                "Please check your configuration files."
            )

        prusalink_config = self._config["prusalink"]
        return dict(prusalink_config)

    def list_sources(self) -> List[Path]:
        """List all configuration sources that were loaded.

        Returns:
            List of configuration file paths that were successfully loaded
        """
        if self._config is None:
            self.load()
        return self._config_sources.copy()

    def to_dict(self) -> Dict[str, Any]:
        """Convert the merged configuration to a dictionary.

        Returns:
            Dictionary representation of the configuration
        """
        if self._config is None:
            self.load()
        return self._config.as_dict()


# Global instance for easy access
_secrets_config: Optional[SecretsConfig] = None


def get_secrets_config() -> SecretsConfig:
    """Get the global secrets configuration instance.

    Returns:
        Global SecretsConfig instance
    """
    global _secrets_config
    if _secrets_config is None:
        _secrets_config = SecretsConfig()
    return _secrets_config


def load_prusalink_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load PrusaLink configuration with hierarchical support.

    Args:
        config_path: Optional specific config file path (for backward compatibility)

    Returns:
        PrusaLink configuration dictionary

    Raises:
        FileNotFoundError: If no configuration files are found
        KeyError: If prusalink section is not found
    """
    if config_path:
        # Backward compatibility: load specific file
        import toml

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, "r") as f:
            config = toml.load(f)

        if "prusalink" not in config:
            raise KeyError(f"No 'prusalink' section found in {config_path}")

        return config["prusalink"]
    else:
        # Use hierarchical configuration
        secrets_config = get_secrets_config()
        return secrets_config.get_prusalink_config()
