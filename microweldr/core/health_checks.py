"""System health checks and monitoring utilities."""

import logging
import platform
import shutil
import subprocess  # nosec B404 - Used for system health checks only
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .graceful_degradation import ResilientPrusaLinkClient

logger = logging.getLogger(__name__)


class HealthChecker:
    """Comprehensive system health checker."""

    def __init__(self):
        """Initialize health checker."""
        self.checks = {}
        self.warnings = []
        self.errors = []

    def run_all_checks(self, secrets_path: Optional[str] = None) -> Dict[str, Any]:
        """Run all health checks.

        Args:
            secrets_path: Path to secrets file for printer checks

        Returns:
            Health status dictionary
        """
        self.checks.clear()
        self.warnings.clear()
        self.errors.clear()

        # Core system checks
        self.checks["python"] = self._check_python_version()
        self.checks["dependencies"] = self._check_dependencies()
        self.checks["filesystem"] = self._check_filesystem_access()
        self.checks["memory"] = self._check_memory_usage()
        self.checks["disk_space"] = self._check_disk_space()

        # Application-specific checks
        self.checks["configuration"] = self._check_configuration()
        self.checks["logging"] = self._check_logging_system()
        self.checks["validation"] = self._check_validation_tools()

        # Printer connectivity (if secrets provided)
        if secrets_path and Path(secrets_path).exists():
            self.checks["printer"] = self._check_printer_connectivity(secrets_path)
        else:
            self.checks["printer"] = {
                "status": "skipped",
                "message": "No secrets file provided",
            }

        # Determine overall health
        overall_status = self._determine_overall_health()

        return {
            "overall": overall_status,
            "timestamp": time.time(),
            "system_info": self._get_system_info(),
            "checks": self.checks,
            "warnings": self.warnings,
            "errors": self.errors,
            "recommendations": self._generate_recommendations(),
        }

    def _check_python_version(self) -> Dict[str, Any]:
        """Check Python version compatibility."""
        version_info = sys.version_info
        version_str = f"{version_info.major}.{version_info.minor}.{version_info.micro}"

        if version_info < (3, 8):
            self.errors.append(f"Python {version_str} is too old (minimum: 3.8)")
            return {
                "status": "error",
                "version": version_str,
                "message": "Python version too old",
            }
        elif version_info < (3, 9):
            self.warnings.append(
                f"Python {version_str} is supported but newer versions recommended"
            )
            return {
                "status": "warning",
                "version": version_str,
                "message": "Consider upgrading Python",
            }
        else:
            return {
                "status": "healthy",
                "version": version_str,
                "message": "Python version is compatible",
            }

    def _check_dependencies(self) -> Dict[str, Any]:
        """Check required dependencies."""
        required_packages = {
            "toml": "Configuration parsing",
            "requests": "HTTP communication",
            "lxml": "SVG validation",
            "pathlib": "File path handling",
        }

        optional_packages = {
            "gcodeparser": "G-code validation",
            "pygcode": "G-code parsing",
            "xmlschema": "XML schema validation",
            "hypothesis": "Property-based testing",
            "click": "Enhanced CLI",
            "tqdm": "Progress bars",
        }

        missing_required = []
        missing_optional = []

        # Check required packages
        for package, description in required_packages.items():
            try:
                __import__(package)
            except ImportError:
                missing_required.append(f"{package} ({description})")

        # Check optional packages
        for package, description in optional_packages.items():
            try:
                __import__(package)
            except ImportError:
                missing_optional.append(f"{package} ({description})")

        if missing_required:
            self.errors.extend(
                [f"Missing required package: {pkg}" for pkg in missing_required]
            )
            return {
                "status": "error",
                "missing_required": missing_required,
                "missing_optional": missing_optional,
                "message": f"{len(missing_required)} required packages missing",
            }
        elif missing_optional:
            self.warnings.extend(
                [f"Missing optional package: {pkg}" for pkg in missing_optional]
            )
            return {
                "status": "warning",
                "missing_required": [],
                "missing_optional": missing_optional,
                "message": f"{len(missing_optional)} optional packages missing",
            }
        else:
            return {
                "status": "healthy",
                "missing_required": [],
                "missing_optional": [],
                "message": "All dependencies available",
            }

    def _check_filesystem_access(self) -> Dict[str, Any]:
        """Check filesystem read/write access."""
        import tempfile

        test_paths = [
            Path.cwd(),  # Current directory
            Path.cwd() / "logs",  # Logs directory
            Path(tempfile.gettempdir()),  # Secure temp directory
        ]

        access_issues = []

        for path in test_paths:
            try:
                # Test directory creation
                if not path.exists():
                    path.mkdir(parents=True, exist_ok=True)

                # Test file write
                test_file = path / f"health_check_{time.time()}.tmp"
                test_file.write_text("test")

                # Test file read
                content = test_file.read_text()
                if content != "test":
                    access_issues.append(f"Read/write mismatch in {path}")

                # Clean up
                test_file.unlink()

            except Exception as e:
                access_issues.append(f"Cannot access {path}: {e}")

        if access_issues:
            self.errors.extend(access_issues)
            return {
                "status": "error",
                "issues": access_issues,
                "message": f"{len(access_issues)} filesystem access issues",
            }
        else:
            return {
                "status": "healthy",
                "issues": [],
                "message": "Filesystem access is working",
            }

    def _check_memory_usage(self) -> Dict[str, Any]:
        """Check memory usage."""
        try:
            import psutil

            memory = psutil.virtual_memory()

            available_gb = memory.available / (1024**3)
            percent_used = memory.percent

            if available_gb < 0.5:  # Less than 500MB available
                self.errors.append(f"Very low memory: {available_gb:.1f}GB available")
                return {
                    "status": "error",
                    "available_gb": available_gb,
                    "percent_used": percent_used,
                    "message": "Critically low memory",
                }
            elif available_gb < 1.0:  # Less than 1GB available
                self.warnings.append(f"Low memory: {available_gb:.1f}GB available")
                return {
                    "status": "warning",
                    "available_gb": available_gb,
                    "percent_used": percent_used,
                    "message": "Low memory available",
                }
            else:
                return {
                    "status": "healthy",
                    "available_gb": available_gb,
                    "percent_used": percent_used,
                    "message": f"{available_gb:.1f}GB memory available",
                }

        except ImportError:
            return {
                "status": "skipped",
                "message": "psutil not available for memory checking",
            }
        except Exception as e:
            return {"status": "error", "message": f"Memory check failed: {e}"}

    def _check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space."""
        try:
            current_dir = Path.cwd()
            total, used, free = shutil.disk_usage(current_dir)

            free_gb = free / (1024**3)
            percent_used = (used / total) * 100

            if free_gb < 0.1:  # Less than 100MB free
                self.errors.append(f"Very low disk space: {free_gb:.1f}GB free")
                return {
                    "status": "error",
                    "free_gb": free_gb,
                    "percent_used": percent_used,
                    "message": "Critically low disk space",
                }
            elif free_gb < 1.0:  # Less than 1GB free
                self.warnings.append(f"Low disk space: {free_gb:.1f}GB free")
                return {
                    "status": "warning",
                    "free_gb": free_gb,
                    "percent_used": percent_used,
                    "message": "Low disk space",
                }
            else:
                return {
                    "status": "healthy",
                    "free_gb": free_gb,
                    "percent_used": percent_used,
                    "message": f"{free_gb:.1f}GB disk space available",
                }

        except Exception as e:
            return {"status": "error", "message": f"Disk space check failed: {e}"}

    def _check_configuration(self) -> Dict[str, Any]:
        """Check configuration file validity."""
        config_files = ["config.toml", "examples/config.toml"]
        config_issues = []

        for config_file in config_files:
            config_path = Path(config_file)
            if config_path.exists():
                try:
                    import toml

                    config = toml.load(config_path)

                    # Basic structure validation
                    required_sections = ["printer", "temperatures", "normal_welds"]
                    missing_sections = [s for s in required_sections if s not in config]

                    if missing_sections:
                        config_issues.append(
                            f"{config_file}: missing sections {missing_sections}"
                        )

                except Exception as e:
                    config_issues.append(f"{config_file}: parse error - {e}")

        if not any(Path(f).exists() for f in config_files):
            config_issues.append("No configuration files found")

        if config_issues:
            self.warnings.extend(config_issues)
            return {
                "status": "warning",
                "issues": config_issues,
                "message": f"{len(config_issues)} configuration issues",
            }
        else:
            return {
                "status": "healthy",
                "issues": [],
                "message": "Configuration files are valid",
            }

    def _check_logging_system(self) -> Dict[str, Any]:
        """Check logging system functionality."""
        try:
            # Test logging
            test_logger = logging.getLogger("health_check_test")
            test_logger.info("Health check logging test")

            # Check if logs directory exists and is writable
            logs_dir = Path("logs")
            if logs_dir.exists():
                test_log = logs_dir / "health_check.tmp"
                test_log.write_text("test")
                test_log.unlink()

            return {"status": "healthy", "message": "Logging system is functional"}

        except Exception as e:
            self.warnings.append(f"Logging system issue: {e}")
            return {"status": "warning", "message": f"Logging issue: {e}"}

    def _check_validation_tools(self) -> Dict[str, Any]:
        """Check validation tools availability."""
        validation_tools = {
            "lxml": "SVG validation",
            "gcodeparser": "G-code validation",
            "xmlschema": "XML schema validation",
        }

        available_tools = []
        missing_tools = []

        for tool, description in validation_tools.items():
            try:
                __import__(tool)
                available_tools.append(f"{tool} ({description})")
            except ImportError:
                missing_tools.append(f"{tool} ({description})")

        if len(available_tools) == 0:
            self.errors.append("No validation tools available")
            return {
                "status": "error",
                "available": available_tools,
                "missing": missing_tools,
                "message": "No validation tools available",
            }
        elif missing_tools:
            self.warnings.extend(
                [f"Missing validation tool: {tool}" for tool in missing_tools]
            )
            return {
                "status": "warning",
                "available": available_tools,
                "missing": missing_tools,
                "message": f"{len(available_tools)}/{len(validation_tools)} validation tools available",
            }
        else:
            return {
                "status": "healthy",
                "available": available_tools,
                "missing": [],
                "message": "All validation tools available",
            }

    def _check_printer_connectivity(self, secrets_path: str) -> Dict[str, Any]:
        """Check printer connectivity."""
        try:
            client = ResilientPrusaLinkClient(secrets_path)
            status = client.get_status()

            if status.get("fallback"):
                self.warnings.append("Printer connection degraded (fallback mode)")
                return {
                    "status": "warning",
                    "state": "fallback",
                    "message": "Printer connection degraded",
                }
            else:
                printer_state = status.get("printer", {}).get("state", "Unknown")
                return {
                    "status": "healthy",
                    "state": printer_state,
                    "message": f"Printer connected: {printer_state}",
                }

        except Exception as e:
            self.errors.append(f"Printer connection failed: {e}")
            return {
                "status": "error",
                "state": "disconnected",
                "message": f"Connection failed: {e}",
            }

    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "architecture": platform.architecture()[0],
            "processor": platform.processor() or "Unknown",
            "hostname": platform.node(),
            "working_directory": str(Path.cwd()),
        }

    def _determine_overall_health(self) -> str:
        """Determine overall system health status."""
        if self.errors:
            return "unhealthy"
        elif self.warnings:
            return "degraded"
        else:
            return "healthy"

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on health check results."""
        recommendations = []

        # Python version recommendations
        if self.checks.get("python", {}).get("status") == "warning":
            recommendations.append(
                "Consider upgrading to Python 3.10+ for better performance"
            )

        # Memory recommendations
        memory_check = self.checks.get("memory", {})
        if memory_check.get("status") in ["warning", "error"]:
            recommendations.append("Close other applications to free up memory")
            recommendations.append(
                "Consider processing smaller SVG files or using caching"
            )

        # Disk space recommendations
        disk_check = self.checks.get("disk_space", {})
        if disk_check.get("status") in ["warning", "error"]:
            recommendations.append("Free up disk space by removing unnecessary files")
            recommendations.append(
                "Consider using a different working directory with more space"
            )

        # Dependencies recommendations
        deps_check = self.checks.get("dependencies", {})
        if deps_check.get("missing_optional"):
            recommendations.append(
                "Install optional packages for enhanced functionality:"
            )
            for pkg in deps_check.get("missing_optional", []):
                recommendations.append(f"  pip install {pkg.split()[0]}")

        # Configuration recommendations
        config_check = self.checks.get("configuration", {})
        if config_check.get("status") == "warning":
            recommendations.append(
                "Run 'microweldr validate config.toml' to fix configuration issues"
            )

        # Printer recommendations
        printer_check = self.checks.get("printer", {})
        if printer_check.get("status") == "error":
            recommendations.append(
                "Check printer network connection and PrusaLink settings"
            )
            recommendations.append(
                "Verify secrets.toml contains correct printer credentials"
            )
        elif printer_check.get("status") == "skipped":
            recommendations.append(
                "Run 'microweldr init-secrets' to set up printer connectivity"
            )

        # Security recommendations
        secrets_check = self.checks.get("secrets", {})
        if secrets_check.get("status") in ["warning", "error"]:
            recommendations.append("Review and fix secrets file security issues")
            recommendations.append(
                "Ensure secrets.toml has restricted file permissions (600)"
            )

        return recommendations


def quick_health_check() -> Tuple[str, List[str]]:
    """Perform a quick health check.

    Returns:
        Tuple of (overall_status, critical_issues)
    """
    checker = HealthChecker()

    # Run only critical checks
    critical_checks = {
        "python": checker._check_python_version(),
        "filesystem": checker._check_filesystem_access(),
        "dependencies": checker._check_dependencies(),
    }

    critical_issues = []
    has_errors = False

    for check_name, result in critical_checks.items():
        if result.get("status") == "error":
            has_errors = True
            critical_issues.append(
                f"{check_name}: {result.get('message', 'Unknown error')}"
            )

    overall_status = "unhealthy" if has_errors else "healthy"
    return overall_status, critical_issues


def monitor_system_health(interval: int = 300, log_results: bool = True) -> None:
    """Monitor system health continuously.

    Args:
        interval: Check interval in seconds
        log_results: Whether to log results
    """
    checker = HealthChecker()

    logger.info(f"Starting system health monitoring (interval: {interval}s)")

    try:
        while True:
            start_time = time.time()

            # Run health checks
            health_status = checker.run_all_checks()

            if log_results:
                overall = health_status["overall"]
                error_count = len(health_status["errors"])
                warning_count = len(health_status["warnings"])

                logger.info(
                    f"Health check: {overall} "
                    f"({error_count} errors, {warning_count} warnings)"
                )

                if health_status["errors"]:
                    for error in health_status["errors"]:
                        logger.error(f"Health issue: {error}")

            # Sleep until next check
            elapsed = time.time() - start_time
            sleep_time = max(0, interval - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("Health monitoring stopped by user")
    except Exception as e:
        logger.error(f"Health monitoring failed: {e}")


def generate_health_report(output_path: Optional[str] = None) -> str:
    """Generate a comprehensive health report.

    Args:
        output_path: Optional path to save report

    Returns:
        Health report as string
    """
    checker = HealthChecker()
    health_status = checker.run_all_checks()

    # Generate report
    report_lines = [
        "MicroWeldr System Health Report",
        "=" * 40,
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Overall Status: {health_status['overall'].upper()}",
        "",
        "System Information:",
        f"  Platform: {health_status['system_info']['platform']}",
        f"  Python: {health_status['system_info']['python_version']}",
        f"  Architecture: {health_status['system_info']['architecture']}",
        f"  Working Directory: {health_status['system_info']['working_directory']}",
        "",
        "Health Checks:",
    ]

    for check_name, result in health_status["checks"].items():
        status = result.get("status", "unknown").upper()
        message = result.get("message", "No message")
        report_lines.append(f"  {check_name.title()}: {status} - {message}")

    if health_status["errors"]:
        report_lines.extend(
            ["", "Errors:", *[f"  • {error}" for error in health_status["errors"]]]
        )

    if health_status["warnings"]:
        report_lines.extend(
            [
                "",
                "Warnings:",
                *[f"  • {warning}" for warning in health_status["warnings"]],
            ]
        )

    if health_status["recommendations"]:
        report_lines.extend(
            [
                "",
                "Recommendations:",
                *[f"  • {rec}" for rec in health_status["recommendations"]],
            ]
        )

    report = "\n".join(report_lines)

    if output_path:
        Path(output_path).write_text(report)
        logger.info(f"Health report saved: {output_path}")

    return report
