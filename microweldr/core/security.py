"""Security validation and checks for secrets and configuration."""

import ipaddress
import logging
import re
import secrets
import string
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import toml

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Raised when security validation fails."""

    pass


class SecretsValidator:
    """Validates secrets and configuration for security compliance."""

    # Common weak passwords to check against
    WEAK_PASSWORDS = {
        "password",
        "123456",
        "admin",
        "root",
        "user",
        "guest",
        "test",
        "default",
        "changeme",
        "welcome",
        "qwerty",
        "abc123",
        "letmein",
        "monkey",
        "dragon",
        "master",
        "shadow",
        "superman",
        "michael",
    }

    # Default/example credentials that should be changed
    DEFAULT_CREDENTIALS = {
        ("admin", "admin"),
        ("admin", "password"),
        ("user", "user"),
        ("maker", "maker"),
        ("prusa", "prusa"),
        ("test", "test"),
    }

    def __init__(self):
        """Initialize secrets validator."""
        self.warnings: List[str] = []
        self.errors: List[str] = []

    def validate_password_strength(
        self, password: str, username: str = None
    ) -> Tuple[bool, List[str]]:
        """Validate password strength.

        Args:
            password: Password to validate
            username: Username (to check for similarity)

        Returns:
            Tuple of (is_strong, issues)
        """
        issues = []

        if not password:
            issues.append("Password cannot be empty")
            return False, issues

        # Check length
        if len(password) < 8:
            issues.append("Password should be at least 8 characters long")

        # Check for weak passwords
        if password.lower() in self.WEAK_PASSWORDS:
            issues.append("Password is too common and easily guessable")

        # Check similarity to username
        if username and password.lower() == username.lower():
            issues.append("Password should not be the same as username")

        # Check character diversity
        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)

        char_types = sum([has_lower, has_upper, has_digit, has_special])

        if char_types < 2:
            issues.append(
                "Password should contain at least 2 different character types (lowercase, uppercase, digits, special characters)"
            )

        # Check for repeated characters
        if len(set(password)) < len(password) * 0.6:
            issues.append("Password contains too many repeated characters")

        # Check for sequential characters (longer patterns only)
        sequential_patterns = ["1234", "abcd", "qwer", "asdf", "zxcv"]
        if any(pattern in password.lower() for pattern in sequential_patterns):
            issues.append("Password contains sequential characters")

        is_strong = len(issues) == 0
        return is_strong, issues

    def validate_ip_address(self, ip_str: str) -> Tuple[bool, Optional[str]]:
        """Validate IP address format and security.

        Args:
            ip_str: IP address string

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            ip = ipaddress.ip_address(ip_str)

            # Check for obviously invalid addresses
            if ip.is_loopback and ip_str not in ["127.0.0.1", "::1"]:
                return False, f"Invalid loopback address: {ip_str}"

            if ip.is_multicast:
                return False, f"Multicast addresses not allowed: {ip_str}"

            if ip.is_reserved and not ip.is_private and not ip.is_loopback:
                return False, f"Reserved address not allowed: {ip_str}"

            # Warn about public IPs (might be intentional but worth noting)
            if not ip.is_private and not ip.is_loopback:
                logger.warning(
                    f"Using public IP address: {ip_str} - ensure this is intentional"
                )

            return True, None

        except ValueError as e:
            return False, f"Invalid IP address format: {e}"

    def validate_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """Validate URL format and security.

        Args:
            url: URL to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            parsed = urlparse(url)

            # Check scheme
            if parsed.scheme not in ["http", "https"]:
                return False, f"Only HTTP/HTTPS URLs are allowed, got: {parsed.scheme}"

            # Warn about HTTP (not HTTPS)
            if parsed.scheme == "http":
                logger.warning(f"Using unencrypted HTTP connection: {url}")

            # Check hostname
            if not parsed.hostname:
                return False, "URL must contain a valid hostname"

            # Validate IP if hostname is an IP address
            try:
                is_valid, error = self.validate_ip_address(parsed.hostname)
                if not is_valid:
                    return False, error
            except:
                # Not an IP address, validate as hostname
                if not re.match(
                    r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$",
                    parsed.hostname,
                ):
                    return False, f"Invalid hostname format: {parsed.hostname}"

            # Check port
            if parsed.port:
                if not (1 <= parsed.port <= 65535):
                    return False, f"Invalid port number: {parsed.port}"

                # Warn about non-standard ports
                standard_ports = {80, 443, 8080, 8443}
                if parsed.port not in standard_ports:
                    logger.info(f"Using non-standard port: {parsed.port}")

            return True, None

        except Exception as e:
            return False, f"Invalid URL format: {e}"

    def validate_secrets_file(self, secrets_path: str) -> Tuple[List[str], List[str]]:
        """Validate secrets configuration file.

        Args:
            secrets_path: Path to secrets file

        Returns:
            Tuple of (warnings, errors)
        """
        self.warnings.clear()
        self.errors.clear()

        secrets_path = Path(secrets_path)

        # Check file existence and permissions
        if not secrets_path.exists():
            self.errors.append(f"Secrets file not found: {secrets_path}")
            return self.warnings.copy(), self.errors.copy()

        # Check file permissions (Unix-like systems)
        try:
            import stat

            file_stat = secrets_path.stat()
            file_mode = stat.filemode(file_stat.st_mode)

            # Check if file is readable by others
            if file_stat.st_mode & stat.S_IROTH:
                self.warnings.append(
                    f"Secrets file is readable by others: {secrets_path}"
                )

            # Check if file is writable by others
            if file_stat.st_mode & stat.S_IWOTH:
                self.errors.append(
                    f"Secrets file is writable by others: {secrets_path}"
                )

        except (AttributeError, OSError):
            # Windows or other systems where stat doesn't work as expected
            logger.debug("Could not check file permissions")

        # Load and validate content
        try:
            config = toml.load(secrets_path)
        except Exception as e:
            self.errors.append(f"Failed to parse secrets file: {e}")
            return self.warnings.copy(), self.errors.copy()

        # Validate PrusaLink configuration
        if "prusalink" in config:
            self._validate_prusalink_config(config["prusalink"])
        else:
            self.warnings.append("No PrusaLink configuration found")

        return self.warnings.copy(), self.errors.copy()

    def _validate_prusalink_config(self, prusalink_config: Dict) -> None:
        """Validate PrusaLink-specific configuration.

        Args:
            prusalink_config: PrusaLink configuration dictionary
        """
        # Check required fields
        required_fields = ["host", "username"]
        for field in required_fields:
            if field not in prusalink_config:
                self.errors.append(f"Missing required PrusaLink field: {field}")

        # Validate host
        if "host" in prusalink_config:
            host = prusalink_config["host"]

            # Check if it's an IP address
            try:
                is_valid, error = self.validate_ip_address(host)
                if not is_valid:
                    self.errors.append(f"PrusaLink host: {error}")
            except:
                # Not an IP, validate as hostname
                if not re.match(
                    r"^[a-zA-Z0-9]([a-zA-Z0-9\-\.]{0,253}[a-zA-Z0-9])?$", host
                ):
                    self.errors.append(f"Invalid PrusaLink hostname: {host}")

        # Validate credentials
        username = prusalink_config.get("username", "")
        password = prusalink_config.get("password", "")
        api_key = prusalink_config.get("api_key", "")

        if not password and not api_key:
            self.errors.append(
                "PrusaLink configuration must include either 'password' or 'api_key'"
            )

        # Check for default credentials
        if (username, password) in self.DEFAULT_CREDENTIALS:
            self.errors.append(
                f"Default credentials detected: {username}/{password} - please change them"
            )

        # Validate password strength if present
        if password:
            is_strong, issues = self.validate_password_strength(password, username)
            if not is_strong:
                for issue in issues:
                    self.warnings.append(f"PrusaLink password: {issue}")

        # Validate API key format if present
        if api_key:
            if len(api_key) < 16:
                self.warnings.append("PrusaLink API key seems too short")

            if not re.match(r"^[a-zA-Z0-9_-]+$", api_key):
                self.warnings.append("PrusaLink API key contains unusual characters")

        # Check timeout value
        if "timeout" in prusalink_config:
            timeout = prusalink_config["timeout"]
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                self.errors.append(f"Invalid timeout value: {timeout}")
            elif timeout < 5:
                self.warnings.append(
                    f"Very short timeout: {timeout}s - may cause connection issues"
                )
            elif timeout > 300:
                self.warnings.append(
                    f"Very long timeout: {timeout}s - may cause hanging"
                )

    def generate_secure_password(self, length: int = 16) -> str:
        """Generate a secure random password.

        Args:
            length: Password length

        Returns:
            Secure random password
        """
        if length < 8:
            raise ValueError("Password length must be at least 8 characters")

        # Ensure we have at least one character from each category
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        special = "!@#$%^&*()_+-="

        # Start with one character from each category
        password = [
            secrets.choice(lowercase),
            secrets.choice(uppercase),
            secrets.choice(digits),
            secrets.choice(special),
        ]

        # Fill the rest randomly
        all_chars = lowercase + uppercase + digits + special
        for _ in range(length - 4):
            password.append(secrets.choice(all_chars))

        # Shuffle the password
        secrets.SystemRandom().shuffle(password)

        return "".join(password)

    def generate_api_key(self, length: int = 32) -> str:
        """Generate a secure API key.

        Args:
            length: API key length

        Returns:
            Secure random API key
        """
        alphabet = string.ascii_letters + string.digits + "_-"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def check_file_safety(self, file_path: str) -> Tuple[bool, List[str]]:
        """Check if a file path is safe to use.

        Args:
            file_path: File path to check

        Returns:
            Tuple of (is_safe, issues)
        """
        issues = []
        path = Path(file_path)

        try:
            # Resolve path to check for directory traversal
            resolved_path = path.resolve()

            # Check for directory traversal attempts
            if ".." in str(path):
                issues.append("Path contains directory traversal sequences (..)")

            # Check for absolute paths that might be dangerous
            dangerous_paths = ["/etc", "/usr", "/bin", "/sbin", "/root", "/home"]
            if path.is_absolute():
                for dangerous in dangerous_paths:
                    if str(resolved_path).startswith(dangerous):
                        issues.append(
                            f"Path accesses potentially dangerous directory: {dangerous}"
                        )

            # Check filename for dangerous characters
            if path.name:
                dangerous_chars = ["<", ">", ":", '"', "|", "?", "*"]
                if any(char in path.name for char in dangerous_chars):
                    issues.append("Filename contains potentially dangerous characters")

            # Check for excessively long paths
            if len(str(resolved_path)) > 260:  # Windows MAX_PATH limit
                issues.append("Path is excessively long and may cause issues")

        except (OSError, ValueError) as e:
            issues.append(f"Path resolution failed: {e}")

        is_safe = len(issues) == 0
        return is_safe, issues

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize a filename to make it safe for filesystem use.

        Args:
            filename: The filename to sanitize

        Returns:
            A safe filename with dangerous characters removed/replaced
        """
        if not filename:
            return "unnamed_file"

        # Remove path traversal attempts
        filename = filename.replace("..", "")
        filename = filename.replace("/", "_")
        filename = filename.replace("\\", "_")

        # Remove or replace dangerous characters
        dangerous_chars = '<>:"|?*\x00-\x1f'
        for char in dangerous_chars:
            filename = filename.replace(char, "_")

        # Remove HTML/script tags and dangerous keywords
        filename = re.sub(r"<[^>]*>", "", filename)
        filename = re.sub(r"script", "", filename, flags=re.IGNORECASE)
        filename = re.sub(r"javascript", "", filename, flags=re.IGNORECASE)

        # Limit length and ensure it's not empty
        filename = filename.strip()[:255]
        if not filename:
            filename = "sanitized_file"

        # Ensure it doesn't start with dangerous prefixes
        if filename.startswith((".", "-")):
            filename = "safe_" + filename

        return filename


def validate_secrets_interactive(secrets_path: str) -> bool:
    """Interactively validate secrets with user prompts.

    Args:
        secrets_path: Path to secrets file

    Returns:
        True if validation passed or was fixed, False otherwise
    """
    validator = SecretsValidator()
    warnings, errors = validator.validate_secrets_file(secrets_path)

    if not errors and not warnings:
        print("✅ Secrets validation passed - configuration is secure")
        return True

    print(f"\n🔍 Security validation results for: {secrets_path}")
    print("=" * 60)

    if warnings:
        print(f"\n⚠️  Warnings ({len(warnings)}):")
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. {warning}")

    if errors:
        print(f"\n❌ Errors ({len(errors)}):")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")

    print("\n" + "=" * 60)

    if errors:
        print("❌ Critical security issues found. Please fix these before proceeding.")
        return False

    if warnings:
        try:
            response = (
                input("\n⚠️  Security warnings found. Continue anyway? (y/N): ")
                .strip()
                .lower()
            )
            return response in ["y", "yes"]
        except (EOFError, KeyboardInterrupt):
            return False

    return True


def create_secure_secrets_template(output_path: str) -> None:
    """Create a secure secrets template file.

    Args:
        output_path: Path for the template file
    """
    validator = SecretsValidator()

    template_content = f"""# MicroWeldr Secrets Configuration
# This file contains sensitive information - keep it secure!
# File permissions should be 600 (readable only by owner)

[prusalink]
# Printer IP address or hostname
host = "192.168.1.100"

# PrusaLink username
username = "maker"

# Use EITHER password OR api_key (not both)
# Password for LCD/web interface authentication
password = "{validator.generate_secure_password()}"

# OR API key for API authentication (more secure)
# api_key = "{validator.generate_api_key()}"

# Connection timeout in seconds
timeout = 30

# Security Notes:
# 1. Change the default password above to something unique
# 2. Consider using API key instead of password for better security
# 3. Ensure this file is not readable by other users
# 4. Never commit this file to version control
# 5. Use HTTPS if your printer supports it
"""

    output_path = Path(output_path)
    output_path.write_text(template_content)

    # Set restrictive permissions on Unix-like systems
    try:
        import stat

        output_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600 permissions
        logger.info(f"Set secure permissions on {output_path}")
    except (AttributeError, OSError):
        logger.warning(f"Could not set secure permissions on {output_path}")

    print(f"✅ Created secure secrets template: {output_path}")
    print("⚠️  Please review and customize the generated passwords/keys")
    print("🔒 File permissions set to be readable only by owner")
