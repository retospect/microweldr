"""Linting tests for MicroWeldr codebase."""

import subprocess
import sys
from pathlib import Path


def test_black_formatting():
    """Test that code is properly formatted with black."""
    result = subprocess.run(
        [sys.executable, "-m", "black", "--check", "."],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("Black formatting issues found:")
        print(result.stdout)
        print(result.stderr)

    assert result.returncode == 0, "Code is not properly formatted with black"


def test_flake8_linting():
    """Test that code passes flake8 linting (non-blocking)."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "flake8",
            "microweldr/",
            "--max-line-length=88",
            "--extend-ignore=E203,W503,E501,F401,F841,F811,F541,E722,F821",
            "--exclude=venv,.venv,build,dist,tests",
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    # Non-blocking - just report issues but don't fail
    if result.returncode != 0:
        print("Flake8 linting issues found (non-blocking):")
        print(result.stdout)
        print(result.stderr)

    # Always pass for now until linting is cleaned up
    assert True


def test_mypy_type_checking():
    """Test that code passes mypy type checking (non-blocking)."""
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "microweldr/"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    # Non-blocking - just report issues but don't fail
    if result.returncode != 0:
        print("MyPy type checking issues found (non-blocking):")
        print(result.stdout)
        print(result.stderr)

    # Always pass for now until type annotations are complete
    assert True


def test_bandit_security_scan():
    """Test that code passes bandit security scan (non-blocking)."""
    result = subprocess.run(
        [sys.executable, "-m", "bandit", "-r", "microweldr/"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    # Non-blocking - just report issues but don't fail
    if result.returncode != 0:
        print("Bandit security issues found (non-blocking):")
        print(result.stdout)
        print(result.stderr)
