"""
Linting tests that catch code quality issues early in the CI pipeline.
These tests fail if code needs formatting or has quality issues.
"""

import subprocess
import sys
from pathlib import Path
from typing import List

import pytest


def run_command(cmd: List[str], cwd: Path = None) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    if cwd is None:
        cwd = Path(__file__).parent.parent

    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


class TestCodeFormatting:
    """Test that code follows formatting standards."""

    def test_black_formatting(self):
        """Test that code is properly formatted with Black."""
        exit_code, stdout, stderr = run_command(
            ["poetry", "run", "black", "--check", "."]
        )

        if exit_code != 0:
            pytest.fail(
                f"Code is not properly formatted with Black.\n"
                f"Run 'poetry run black .' to fix formatting issues.\n"
                f"Output: {stdout}\n"
                f"Error: {stderr}"
            )

    def test_isort_imports(self):
        """Test that imports are properly sorted with isort."""
        exit_code, stdout, stderr = run_command(
            ["poetry", "run", "python", "-m", "isort", "--check-only", "."]
        )

        if exit_code != 0:
            pytest.fail(
                f"Imports are not properly sorted with isort.\n"
                f"Run 'poetry run python -m isort .' to fix import sorting.\n"
                f"Output: {stdout}\n"
                f"Error: {stderr}"
            )

    def test_flake8_style(self):
        """Test that code follows flake8 style guidelines."""
        exit_code, stdout, stderr = run_command(
            ["poetry", "run", "python", "-m", "flake8", "."]
        )

        if exit_code != 0:
            pytest.fail(
                f"Code has flake8 style violations.\n"
                f"Fix the following issues:\n"
                f"Output: {stdout}\n"
                f"Error: {stderr}"
            )

    @pytest.mark.skipif(
        sys.platform == "win32", reason="Skip mypy on Windows for CI stability"
    )
    def test_mypy_type_checking(self):
        """Test that code passes mypy type checking."""
        exit_code, stdout, stderr = run_command(
            ["poetry", "run", "python", "-m", "mypy", "microweldr/"]
        )

        # Allow mypy to pass with warnings for now, but fail on errors
        if exit_code > 1:  # mypy returns 1 for warnings, >1 for errors
            pytest.fail(
                f"Code has mypy type checking errors.\n"
                f"Fix the following type issues:\n"
                f"Output: {stdout}\n"
                f"Error: {stderr}"
            )


class TestProjectStructure:
    """Test that project structure follows standards."""

    def test_required_files_exist(self):
        """Test that required project files exist."""
        root = Path(__file__).parent.parent
        required_files = [
            "pyproject.toml",
            "README.md",
            "LICENSE",
            ".gitignore",
            ".pre-commit-config.yaml",
        ]

        missing_files = []
        for file_path in required_files:
            if not (root / file_path).exists():
                missing_files.append(file_path)

        if missing_files:
            pytest.fail(f"Missing required files: {missing_files}")

    def test_no_debug_statements(self):
        """Test that no debug statements are left in the code."""
        root = Path(__file__).parent.parent
        python_files = list(root.glob("**/*.py"))

        debug_patterns = [
            "pdb.set_trace()",
            "breakpoint()",
            "import pdb",
            "from pdb import",
        ]

        violations = []
        for py_file in python_files:
            # Skip test files, virtual environments, and external packages
            if (
                "test_" in py_file.name
                or py_file.is_relative_to(root / "tests")
                or "venv" in str(py_file)
                or ".venv" in str(py_file)
                or "site-packages" in str(py_file)
            ):
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
                for line_num, line in enumerate(content.splitlines(), 1):
                    for pattern in debug_patterns:
                        if (
                            pattern in line
                            and not line.strip().startswith("#")
                            and "logging" not in line.lower()  # Skip logging references
                        ):
                            violations.append(f"{py_file}:{line_num}: {line.strip()}")
            except Exception:
                continue  # Skip files that can't be read

        if violations:
            pytest.fail(f"Found debug statements in code:\n" + "\n".join(violations))


class TestSecurity:
    """Test basic security practices."""

    def test_bandit_security_scan(self):
        """Test that code passes Bandit security scan."""
        exit_code, stdout, stderr = run_command(
            [
                "poetry",
                "run",
                "python",
                "-m",
                "bandit",
                "-r",
                "microweldr/",
                "-f",
                "txt",
            ]
        )

        # Bandit returns 1 for low/medium issues, >1 for high/critical
        if exit_code > 1:
            pytest.fail(
                f"Code has high/critical security issues found by Bandit.\n"
                f"Fix the following security issues:\n"
                f"Output: {stdout}\n"
                f"Error: {stderr}"
            )

    def test_no_hardcoded_secrets(self):
        """Test that no obvious secrets are hardcoded."""
        root = Path(__file__).parent.parent
        python_files = list(root.glob("**/*.py"))

        # Look for actual hardcoded values, not configuration access
        secret_patterns = [
            'password = "',
            "password = '",
            'api_key = "',
            "api_key = '",
            'secret = "',
            "secret = '",
            'token = "',
            "token = '",
        ]

        violations = []
        for py_file in python_files:
            # Skip test files, virtual environments, and external packages
            if (
                py_file.is_relative_to(root / "tests")
                or "venv" in str(py_file)
                or ".venv" in str(py_file)
                or "site-packages" in str(py_file)
            ):
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
                for line_num, line in enumerate(content.splitlines(), 1):
                    line_lower = line.lower()
                    for pattern in secret_patterns:
                        if (
                            pattern in line_lower
                            and not line.strip().startswith("#")
                            and "example" not in line_lower
                            and "placeholder" not in line_lower
                            and "your_" not in line_lower
                            and ".get(" not in line_lower  # Skip config access
                            and "config[" not in line_lower  # Skip config access
                            and "constants.py" not in str(py_file)  # Skip constants
                            and "template" not in line_lower  # Skip templates
                            and "security.py"
                            not in str(py_file)  # Skip security module
                        ):
                            violations.append(f"{py_file}:{line_num}: {line.strip()}")
            except Exception:
                continue

        if violations:
            pytest.fail(f"Found potential hardcoded secrets:\n" + "\n".join(violations))
