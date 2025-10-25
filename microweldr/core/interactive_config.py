"""Interactive configuration validation and setup utilities."""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click
import toml

from .safety import SafetyValidator
from .security import SecretsValidator

logger = logging.getLogger(__name__)


class InteractiveConfigValidator:
    """Interactive configuration validator with user prompts and fixes."""

    def __init__(self):
        """Initialize interactive validator."""
        self.safety_validator = SafetyValidator()
        self.secrets_validator = SecretsValidator()
        self.fixes_applied = []

    def validate_config_interactive(self, config_path: str) -> bool:
        """Interactively validate configuration with user prompts.

        Args:
            config_path: Path to configuration file

        Returns:
            True if validation passed or was fixed, False otherwise
        """
        config_path = Path(config_path)

        if not config_path.exists():
            click.echo(f"❌ Configuration file not found: {config_path}")
            if click.confirm("Create a default configuration file?"):
                self._create_default_config(config_path)
                click.echo(f"✅ Created default configuration: {config_path}")
                return True
            return False

        try:
            config = toml.load(config_path)
        except Exception as e:
            click.echo(f"❌ Failed to parse configuration file: {e}")
            return False

        click.echo(f"\n🔍 Validating configuration: {config_path}")
        click.echo("=" * 60)

        # Validate safety parameters
        warnings, errors = self.safety_validator.validate_config(config)

        if errors:
            click.echo(f"\n❌ Configuration errors found ({len(errors)}):")
            for i, error in enumerate(errors, 1):
                click.echo(f"  {i}. {error}")

            if click.confirm("\n🔧 Attempt to fix configuration errors automatically?"):
                fixed_config = self._fix_config_errors(config, errors)
                if fixed_config:
                    self._save_config_with_backup(config_path, fixed_config)
                    click.echo("✅ Configuration errors fixed")
                    config = fixed_config
                    # Re-validate
                    warnings, errors = self.safety_validator.validate_config(config)

        if warnings:
            click.echo(f"\n⚠️  Configuration warnings ({len(warnings)}):")
            for i, warning in enumerate(warnings, 1):
                click.echo(f"  {i}. {warning}")

            if click.confirm("\n🔧 Review and fix warnings interactively?"):
                self._fix_warnings_interactive(config_path, config, warnings)

        # Validate structure completeness
        missing_sections = self._check_missing_sections(config)
        if missing_sections:
            click.echo(
                f"\n⚠️  Missing configuration sections: {', '.join(missing_sections)}"
            )
            if click.confirm("Add missing sections with default values?"):
                self._add_missing_sections(config_path, config, missing_sections)

        # Final validation
        if not errors:
            click.echo("\n✅ Configuration validation completed successfully")
            if self.fixes_applied:
                click.echo("🔧 Applied fixes:")
                for fix in self.fixes_applied:
                    click.echo(f"   • {fix}")
            return True
        else:
            click.echo(f"\n❌ Configuration still has {len(errors)} errors")
            return False

    def _create_default_config(self, config_path: Path) -> None:
        """Create a default configuration file."""
        default_config = {
            "printer": {
                "bed_size_x": 250,
                "bed_size_y": 220,
                "bed_size_z": 270,
                "layed_back_mode": False,
            },
            "nozzle": {"outer_diameter": 1.0, "inner_diameter": 0.4},
            "temperatures": {
                "bed_temperature": 60,
                "nozzle_temperature": 200,
                "chamber_temperature": 35,
                "use_chamber_heating": False,
                "cooldown_temperature": 50,
            },
            "movement": {"move_height": 5.0, "travel_speed": 3000, "z_speed": 600},
            "normal_welds": {
                "weld_height": 0.020,
                "weld_temperature": 100,
                "weld_time": 0.1,
                "dot_spacing": 0.9,
                "initial_dot_spacing": 3.6,
                "cooling_time_between_passes": 2.0,
            },
            "light_welds": {
                "weld_height": 0.020,
                "weld_temperature": 110,
                "weld_time": 0.3,
                "dot_spacing": 0.9,
                "initial_dot_spacing": 3.6,
                "cooling_time_between_passes": 1.5,
            },
            "animation": {
                "time_between_welds": 0.5,
                "pause_time": 2.0,
                "min_animation_duration": 10.0,
            },
            "output": {
                "gcode_extension": ".gcode",
                "animation_extension": "_animation.svg",
            },
        }

        # Ensure parent directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            toml.dump(default_config, f)

    def _fix_config_errors(self, config: Dict, errors: List[str]) -> Optional[Dict]:
        """Attempt to automatically fix configuration errors.

        Args:
            config: Original configuration
            errors: List of error messages

        Returns:
            Fixed configuration or None if couldn't fix
        """
        fixed_config = config.copy()
        fixes_applied = []

        for error in errors:
            if "exceeds maximum safe limit" in error:
                # Extract parameter name and fix excessive values
                if "bed_temperature" in error and "80" in error:
                    fixed_config.setdefault("temperatures", {})["bed_temperature"] = 80
                    fixes_applied.append("Set bed_temperature to safe maximum (80°C)")

                elif "weld_temperature" in error and "120" in error:
                    # Find which weld type and fix
                    if "normal_welds" in error:
                        fixed_config.setdefault("normal_welds", {})[
                            "weld_temperature"
                        ] = 120
                        fixes_applied.append(
                            "Set normal_welds.weld_temperature to safe maximum (120°C)"
                        )
                    elif "light_welds" in error:
                        fixed_config.setdefault("light_welds", {})[
                            "weld_temperature"
                        ] = 120
                        fixes_applied.append(
                            "Set light_welds.weld_temperature to safe maximum (120°C)"
                        )

                elif "weld_height" in error and "0.5" in error:
                    if "normal_welds" in error:
                        fixed_config.setdefault("normal_welds", {})["weld_height"] = 0.5
                        fixes_applied.append(
                            "Set normal_welds.weld_height to safe maximum (0.5mm)"
                        )
                    elif "light_welds" in error:
                        fixed_config.setdefault("light_welds", {})["weld_height"] = 0.5
                        fixes_applied.append(
                            "Set light_welds.weld_height to safe maximum (0.5mm)"
                        )

                elif "weld_time" in error and "5.0" in error:
                    if "normal_welds" in error:
                        fixed_config.setdefault("normal_welds", {})["weld_time"] = 5.0
                        fixes_applied.append(
                            "Set normal_welds.weld_time to safe maximum (5.0s)"
                        )
                    elif "light_welds" in error:
                        fixed_config.setdefault("light_welds", {})["weld_time"] = 5.0
                        fixes_applied.append(
                            "Set light_welds.weld_time to safe maximum (5.0s)"
                        )

                elif "travel_speed" in error and "3000" in error:
                    fixed_config.setdefault("movement", {})["travel_speed"] = 3000
                    fixes_applied.append(
                        "Set travel_speed to safe maximum (3000 mm/min)"
                    )

                elif "z_speed" in error and "1000" in error:
                    fixed_config.setdefault("movement", {})["z_speed"] = 1000
                    fixes_applied.append("Set z_speed to safe maximum (1000 mm/min)")

        if fixes_applied:
            self.fixes_applied.extend(fixes_applied)
            return fixed_config

        return None

    def _fix_warnings_interactive(
        self, config_path: Path, config: Dict, warnings: List[str]
    ) -> None:
        """Interactively fix configuration warnings.

        Args:
            config_path: Path to configuration file
            config: Configuration dictionary
            warnings: List of warning messages
        """
        click.echo("\n🔧 Interactive warning resolution:")

        modified = False

        for i, warning in enumerate(warnings, 1):
            click.echo(f"\n⚠️  Warning {i}: {warning}")

            # Suggest fixes based on warning content
            if "below recommended minimum" in warning:
                if "weld_temperature" in warning:
                    current_temp = self._extract_number_from_warning(warning)
                    suggested_temp = max(current_temp, 50.0)

                    if click.confirm(f"Increase temperature to {suggested_temp}°C?"):
                        section, param = self._find_config_parameter(
                            config, "weld_temperature"
                        )
                        if section and param:
                            config[section][param] = suggested_temp
                            modified = True
                            self.fixes_applied.append(
                                f"Increased {section}.{param} to {suggested_temp}°C"
                            )

                elif "weld_time" in warning:
                    current_time = self._extract_number_from_warning(warning)
                    suggested_time = max(current_time, 0.05)

                    if click.confirm(f"Increase weld time to {suggested_time}s?"):
                        section, param = self._find_config_parameter(
                            config, "weld_time"
                        )
                        if section and param:
                            config[section][param] = suggested_time
                            modified = True
                            self.fixes_applied.append(
                                f"Increased {section}.{param} to {suggested_time}s"
                            )

            elif "Very short timeout" in warning:
                if click.confirm("Increase timeout to recommended 30 seconds?"):
                    config.setdefault("prusalink", {})["timeout"] = 30
                    modified = True
                    self.fixes_applied.append("Increased PrusaLink timeout to 30s")

            elif "Very long timeout" in warning:
                if click.confirm("Reduce timeout to recommended 60 seconds?"):
                    config.setdefault("prusalink", {})["timeout"] = 60
                    modified = True
                    self.fixes_applied.append("Reduced PrusaLink timeout to 60s")

        if modified:
            self._save_config_with_backup(config_path, config)
            click.echo("✅ Configuration updated with warning fixes")

    def _check_missing_sections(self, config: Dict) -> List[str]:
        """Check for missing configuration sections.

        Args:
            config: Configuration dictionary

        Returns:
            List of missing section names
        """
        required_sections = [
            "printer",
            "nozzle",
            "temperatures",
            "movement",
            "normal_welds",
            "light_welds",
            "animation",
            "output",
        ]

        missing = []
        for section in required_sections:
            if section not in config:
                missing.append(section)

        return missing

    def _add_missing_sections(
        self, config_path: Path, config: Dict, missing_sections: List[str]
    ) -> None:
        """Add missing configuration sections with default values.

        Args:
            config_path: Path to configuration file
            config: Configuration dictionary
            missing_sections: List of missing section names
        """
        defaults = {
            "printer": {
                "bed_size_x": 250,
                "bed_size_y": 220,
                "bed_size_z": 270,
                "layed_back_mode": False,
            },
            "nozzle": {"outer_diameter": 1.0, "inner_diameter": 0.4},
            "temperatures": {
                "bed_temperature": 60,
                "nozzle_temperature": 200,
                "chamber_temperature": 35,
                "use_chamber_heating": False,
                "cooldown_temperature": 50,
            },
            "movement": {"move_height": 5.0, "travel_speed": 3000, "z_speed": 600},
            "normal_welds": {
                "weld_height": 0.020,
                "weld_temperature": 100,
                "weld_time": 0.1,
                "dot_spacing": 0.9,
                "initial_dot_spacing": 3.6,
                "cooling_time_between_passes": 2.0,
            },
            "light_welds": {
                "weld_height": 0.020,
                "weld_temperature": 110,
                "weld_time": 0.3,
                "dot_spacing": 0.9,
                "initial_dot_spacing": 3.6,
                "cooling_time_between_passes": 1.5,
            },
            "animation": {
                "time_between_welds": 0.5,
                "pause_time": 2.0,
                "min_animation_duration": 10.0,
            },
            "output": {
                "gcode_extension": ".gcode",
                "animation_extension": "_animation.svg",
            },
        }

        for section in missing_sections:
            if section in defaults:
                config[section] = defaults[section]
                self.fixes_applied.append(f"Added missing section: {section}")

        self._save_config_with_backup(config_path, config)
        click.echo(f"✅ Added {len(missing_sections)} missing sections")

    def _save_config_with_backup(self, config_path: Path, config: Dict) -> None:
        """Save configuration with backup of original.

        Args:
            config_path: Path to configuration file
            config: Configuration dictionary to save
        """
        # Create backup
        backup_path = config_path.with_suffix(config_path.suffix + ".backup")
        if config_path.exists():
            import shutil

            shutil.copy2(config_path, backup_path)
            logger.info(f"Created backup: {backup_path}")

        # Save updated configuration
        with open(config_path, "w") as f:
            toml.dump(config, f)

        logger.info(f"Updated configuration: {config_path}")

    def _extract_number_from_warning(self, warning: str) -> float:
        """Extract numeric value from warning message.

        Args:
            warning: Warning message

        Returns:
            Extracted number or 0.0 if not found
        """
        # Look for patterns like "50.0°C" or "0.05s"
        matches = re.findall(r"(\d+\.?\d*)", warning)
        if matches:
            try:
                return float(matches[0])
            except ValueError:
                pass
        return 0.0

    def _find_config_parameter(
        self, config: Dict, param_name: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Find which section contains a parameter.

        Args:
            config: Configuration dictionary
            param_name: Parameter name to find

        Returns:
            Tuple of (section_name, parameter_name) or (None, None)
        """
        for section_name, section_data in config.items():
            if isinstance(section_data, dict) and param_name in section_data:
                return section_name, param_name
        return None, None


def setup_wizard() -> None:
    """Interactive setup wizard for new installations."""
    click.echo("🧙 MicroWeldr Setup Wizard")
    click.echo("=" * 40)

    # Check for existing configuration
    config_path = Path("config.toml")
    secrets_path = Path("secrets.toml")

    if config_path.exists() or secrets_path.exists():
        click.echo("⚠️  Existing configuration detected:")
        if config_path.exists():
            click.echo(f"   • Configuration: {config_path}")
        if secrets_path.exists():
            click.echo(f"   • Secrets: {secrets_path}")

        if not click.confirm("Continue with setup (may overwrite existing files)?"):
            click.echo("❌ Setup cancelled")
            return

    # Step 1: Create configuration
    click.echo("\n📋 Step 1: Configuration Setup")

    validator = InteractiveConfigValidator()

    if not config_path.exists():
        click.echo("Creating default configuration...")
        validator._create_default_config(config_path)

    # Validate and fix configuration
    validator.validate_config_interactive(str(config_path))

    # Step 2: Printer setup
    click.echo("\n🖨️  Step 2: Printer Setup")

    if click.confirm("Do you want to configure printer connectivity?"):
        _setup_printer_interactive(secrets_path)
    else:
        click.echo(
            "⏭️  Skipping printer setup (you can run 'microweldr init-secrets' later)"
        )

    # Step 3: Test setup
    click.echo("\n🧪 Step 3: Test Configuration")

    if click.confirm("Test the configuration with a sample SVG?"):
        _test_configuration_interactive()

    click.echo("\n🎉 Setup completed successfully!")
    click.echo("\nNext steps:")
    click.echo("   1. Review the generated configuration files")
    click.echo("   2. Test with your own SVG files")
    click.echo("   3. Run 'microweldr status' to check system health")


def _setup_printer_interactive(secrets_path: Path) -> None:
    """Interactive printer setup."""
    click.echo("Setting up printer connectivity...")

    # Get printer details
    host = click.prompt("Printer IP address or hostname", default="192.168.1.100")
    username = click.prompt("PrusaLink username", default="maker")

    # Password or API key
    auth_method = click.prompt(
        "Authentication method",
        type=click.Choice(["password", "api_key"]),
        default="password",
    )

    if auth_method == "password":
        password = click.prompt("PrusaLink password", hide_input=True)
        secrets_config = {
            "prusalink": {
                "host": host,
                "username": username,
                "password": password,
                "timeout": 30,
            }
        }
    else:
        api_key = click.prompt("PrusaLink API key")
        secrets_config = {
            "prusalink": {
                "host": host,
                "username": username,
                "api_key": api_key,
                "timeout": 30,
            }
        }

    # Save secrets
    with open(secrets_path, "w") as f:
        toml.dump(secrets_config, f)

    # Set secure permissions
    try:
        import stat

        secrets_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600 permissions
    except (AttributeError, OSError):
        pass

    click.echo(f"✅ Printer configuration saved: {secrets_path}")

    # Test connection
    if click.confirm("Test printer connection now?"):
        try:
            from .graceful_degradation import ResilientPrusaLinkClient

            client = ResilientPrusaLinkClient(str(secrets_path))
            status = client.get_status()

            if status.get("fallback"):
                click.echo("❌ Connection test failed")
            else:
                state = status.get("printer", {}).get("state", "Unknown")
                click.echo(f"✅ Connection successful - Printer state: {state}")

        except Exception as e:
            click.echo(f"❌ Connection test failed: {e}")


def _test_configuration_interactive() -> None:
    """Interactive configuration testing."""
    click.echo("Testing configuration with sample SVG...")

    # Create a simple test SVG
    test_svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="50" height="50" xmlns="http://www.w3.org/2000/svg">
  <line x1="10" y1="10" x2="40" y2="10" stroke="black" stroke-width="1" />
  <circle cx="25" cy="30" r="5" stroke="blue" stroke-width="1" fill="none" />
</svg>"""

    test_svg_path = Path("test_sample.svg")
    test_svg_path.write_text(test_svg_content)

    try:
        from .svg_parser import SVGParser
        from .config import Config
        from .safety import validate_weld_operation

        # Test parsing
        parser = SVGParser()
        weld_paths = parser.parse_file(test_svg_path)

        if not weld_paths:
            click.echo("❌ Test failed: No weld paths found")
            return

        # Test safety validation
        config = Config("config.toml")
        warnings, errors = validate_weld_operation(weld_paths, config.config)

        if errors:
            click.echo(f"❌ Test failed: {len(errors)} safety errors")
            for error in errors:
                click.echo(f"   • {error}")
        else:
            total_points = sum(len(path.points) for path in weld_paths)
            click.echo(f"✅ Test passed: {len(weld_paths)} paths, {total_points} points")

            if warnings:
                click.echo(f"⚠️  {len(warnings)} warnings (acceptable)")

    except Exception as e:
        click.echo(f"❌ Test failed: {e}")

    finally:
        # Clean up test file
        if test_svg_path.exists():
            test_svg_path.unlink()
