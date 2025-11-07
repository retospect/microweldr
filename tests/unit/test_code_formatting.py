"""Tests for code formatting compliance."""

import subprocess
import sys
from pathlib import Path

import pytest


class TestCodeFormatting:
    """Test suite for code formatting compliance."""

    def get_python_files(self) -> list[Path]:
        """Get all Python files in the project."""
        project_root = Path(__file__).parent.parent.parent
        python_files = []

        # Find all .py files in microweldr and tests directories
        for directory in ["microweldr", "tests"]:
            dir_path = project_root / directory
            if dir_path.exists():
                python_files.extend(dir_path.rglob("*.py"))

        return python_files

    def test_python_files_exist(self):
        """Test that Python files exist in expected directories."""
        python_files = self.get_python_files()
        assert (
            len(python_files) > 0
        ), "No Python files found in microweldr or tests directories"

        # Check that we have files in both main package and tests
        microweldr_files = [f for f in python_files if "microweldr" in f.parts]
        test_files = [f for f in python_files if "tests" in f.parts]

        assert (
            len(microweldr_files) > 0
        ), "No Python files found in microweldr directory"
        assert len(test_files) > 0, "No Python files found in tests directory"

    def test_isort_formatting_compliance(self):
        """Test that all Python files comply with isort import sorting standards."""
        project_root = Path(__file__).parent.parent.parent

        # Run isort --check-only on microweldr and tests directories
        cmd = [
            sys.executable,
            "-m",
            "isort",
            "--check-only",
            "--diff",  # Show what would change
            str(project_root / "microweldr"),
            str(project_root / "tests"),
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=project_root, timeout=30
            )

            # isort returns non-zero if imports need sorting
            if result.returncode != 0:
                error_message = (
                    f"Import sorting check failed. Some files have incorrectly sorted imports.\n"
                    f"Run 'make format' or 'isort microweldr tests' to fix import sorting.\n\n"
                    f"Diff output:\n{result.stdout}"
                )
                pytest.fail(error_message)

        except subprocess.TimeoutExpired:
            pytest.fail("isort check timed out after 30 seconds")
        except FileNotFoundError:
            pytest.skip("isort not available - install with 'pip install isort'")

    def test_no_trailing_whitespace_in_python_files(self):
        """Test that Python files don't have trailing whitespace."""
        python_files = self.get_python_files()
        files_with_trailing_whitespace = []

        for py_file in python_files:
            try:
                content = py_file.read_text(encoding="utf-8")
                lines = content.split("\n")

                for line_num, line in enumerate(lines, 1):
                    # Check for trailing whitespace (but allow empty lines)
                    if line.rstrip() != line and line.strip():
                        files_with_trailing_whitespace.append(f"{py_file}:{line_num}")

            except UnicodeDecodeError:
                # Skip binary files
                continue

        if files_with_trailing_whitespace:
            error_message = (
                f"Found trailing whitespace in {len(files_with_trailing_whitespace)} locations:\n"
                + "\n".join(files_with_trailing_whitespace[:10])
            )
            if len(files_with_trailing_whitespace) > 10:
                error_message += f"\n... and {len(files_with_trailing_whitespace) - 10} more locations"

            pytest.fail(error_message)

    def test_consistent_line_endings_in_python_files(self):
        """Test that Python files use consistent line endings."""
        python_files = self.get_python_files()
        files_with_mixed_endings = []

        for py_file in python_files:
            try:
                content_bytes = py_file.read_bytes()

                # Check for mixed line endings
                has_crlf = b"\r\n" in content_bytes
                has_lf_only = b"\n" in content_bytes and b"\r\n" not in content_bytes
                has_cr_only = b"\r" in content_bytes and b"\r\n" not in content_bytes

                line_ending_types = sum([has_crlf, has_lf_only, has_cr_only])

                if line_ending_types > 1:
                    files_with_mixed_endings.append(str(py_file))

            except Exception:
                # Skip files that can't be read
                continue

        if files_with_mixed_endings:
            error_message = (
                f"Found mixed line endings in {len(files_with_mixed_endings)} files:\n"
                + "\n".join(files_with_mixed_endings)
            )
            pytest.fail(error_message)
