"""Tests for markdown file validation."""

import re
from pathlib import Path
from typing import List, Tuple

import pytest


class TestMarkdownValidation:
    """Test suite for validating markdown files in the project."""

    def get_markdown_files(self) -> List[Path]:
        """Get all markdown files in the project."""
        project_root = Path(__file__).parent.parent.parent
        markdown_files = []

        # Find all .md files in the project
        for md_file in project_root.rglob("*.md"):
            # Skip files in build/dist/venv directories
            if any(part in md_file.parts for part in ['build', 'dist', '.git', '__pycache__', 'venv', '.venv']):
                continue
            markdown_files.append(md_file)

        return markdown_files
    def test_markdown_files_exist(self):
        """Test that expected markdown files exist."""
        project_root = Path(__file__).parent.parent.parent
        expected_files = [project_root / "README.md", project_root / "DEVELOPMENT.md"]

        for file_path in expected_files:
            assert file_path.exists(), f"Expected markdown file not found: {file_path}"

    def test_markdown_files_utf8_encoding(self):
        """Test that all markdown files are properly UTF-8 encoded."""
        markdown_files = self.get_markdown_files()
        assert len(markdown_files) > 0, "No markdown files found"

        for md_file in markdown_files:
            try:
                # Try to read as UTF-8
                content = md_file.read_text(encoding="utf-8")
                assert len(content) > 0, f"Markdown file is empty: {md_file}"
            except UnicodeDecodeError as e:
                pytest.fail(f"File {md_file} is not valid UTF-8: {e}")

    def test_markdown_basic_structure(self):
        """Test that markdown files have basic valid structure."""
        markdown_files = self.get_markdown_files()

        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")

            # Check for basic markdown elements
            lines = content.split("\n")

            # Should have at least one heading
            has_heading = any(line.strip().startswith("#") for line in lines)
            assert has_heading, f"No headings found in {md_file}"

            # Check for unmatched brackets/parentheses in links
            self._validate_markdown_links(content, md_file)

    def test_markdown_code_blocks_closed(self):
        """Test that all code blocks are properly closed."""
        markdown_files = self.get_markdown_files()

        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")

            # Count code block markers
            triple_backticks = content.count("```")
            assert triple_backticks % 2 == 0, f"Unmatched code blocks in {md_file}"

    def test_markdown_no_trailing_whitespace(self):
        """Test that markdown files don't have excessive trailing whitespace."""
        markdown_files = self.get_markdown_files()

        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")
            lines = content.split("\n")

            for line_num, line in enumerate(lines, 1):
                # Allow single trailing space for markdown line breaks
                if len(line) > 0 and line.endswith("  "):
                    continue  # This is intentional markdown line break

                # Check for other trailing whitespace
                if line.rstrip() != line:
                    pytest.fail(f"Trailing whitespace in {md_file}:{line_num}")

    def test_readme_has_required_sections(self):
        """Test that README.md has required sections."""
        project_root = Path(__file__).parent.parent.parent
        readme_path = project_root / "README.md"

        if not readme_path.exists():
            pytest.skip("README.md not found")

        content = readme_path.read_text(encoding="utf-8")

        # Required sections for the project
        required_sections = [
            "Installation",
            "Usage",
            "Configuration",
            "Multi-Pass Welding",
            "Running the Examples",
        ]

        for section in required_sections:
            # Look for section headers (case insensitive)
            pattern = rf"^#+\s*{re.escape(section)}"
            if not re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
                pytest.fail(f"Required section '{section}' not found in README.md")

    def test_development_md_has_required_sections(self):
        """Test that DEVELOPMENT.md has required sections."""
        project_root = Path(__file__).parent.parent.parent
        dev_path = project_root / "DEVELOPMENT.md"

        if not dev_path.exists():
            pytest.skip("DEVELOPMENT.md not found")

        content = dev_path.read_text(encoding="utf-8")

        # Required sections for development guide
        required_sections = [
            "Development Setup",
            "Running Examples",
            "Testing",
            "Code Quality",
        ]

        for section in required_sections:
            pattern = rf"^#+\s*{re.escape(section)}"
            if not re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
                pytest.fail(f"Required section '{section}' not found in DEVELOPMENT.md")

    def test_markdown_links_valid_format(self):
        """Test that markdown links have valid format."""
        markdown_files = self.get_markdown_files()

        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")
            self._validate_markdown_links(content, md_file)

    def test_markdown_no_broken_internal_links(self):
        """Test that internal file references exist."""
        markdown_files = self.get_markdown_files()
        project_root = Path(__file__).parent.parent.parent

        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")

            # Find internal file links (relative paths)
            internal_links = re.findall(r"\[([^\]]+)\]\(([^)]+\.md)\)", content)

            for link_text, link_path in internal_links:
                # Resolve relative to the markdown file's directory
                if not link_path.startswith("http"):
                    full_path = (md_file.parent / link_path).resolve()
                    if not full_path.exists():
                        pytest.fail(f"Broken internal link in {md_file}: {link_path}")

    def _validate_markdown_links(self, content: str, file_path: Path) -> None:
        """Validate markdown link syntax."""
        # Check for unmatched brackets in links
        link_pattern = r"\[([^\]]*)\]\(([^)]*)\)"

        for match in re.finditer(link_pattern, content):
            link_text, link_url = match.groups()

            # Check for empty links
            if not link_text.strip():
                pytest.fail(f"Empty link text in {file_path}: {match.group(0)}")

            # Check for malformed URLs (basic validation)
            if link_url and not link_url.strip():
                pytest.fail(f"Empty link URL in {file_path}: {match.group(0)}")

    def test_markdown_file_sizes_reasonable(self):
        """Test that markdown files are not excessively large."""
        markdown_files = self.get_markdown_files()
        max_size_kb = 500  # 500KB should be plenty for documentation

        for md_file in markdown_files:
            size_kb = md_file.stat().st_size / 1024
            assert (
                size_kb < max_size_kb
            ), f"Markdown file too large: {md_file} ({size_kb:.1f}KB)"

    def test_markdown_consistent_line_endings(self):
        """Test that markdown files use consistent line endings."""
        markdown_files = self.get_markdown_files()

        for md_file in markdown_files:
            # Read as binary to check line endings
            content_bytes = md_file.read_bytes()

            # Check for mixed line endings
            has_crlf = b"\r\n" in content_bytes
            has_lf_only = b"\n" in content_bytes and b"\r\n" not in content_bytes
            has_cr_only = b"\r" in content_bytes and b"\r\n" not in content_bytes

            line_ending_types = sum([has_crlf, has_lf_only, has_cr_only])

            # Should have only one type of line ending
            assert line_ending_types <= 1, f"Mixed line endings in {md_file}"

    def test_markdown_no_tabs(self):
        """Test that markdown files use spaces instead of tabs."""
        markdown_files = self.get_markdown_files()

        for md_file in markdown_files:
            content = md_file.read_text(encoding="utf-8")

            if "\t" in content:
                # Find line numbers with tabs
                lines_with_tabs = []
                for line_num, line in enumerate(content.split("\n"), 1):
                    if "\t" in line:
                        lines_with_tabs.append(line_num)

                if lines_with_tabs:
                    pytest.fail(f"Tabs found in {md_file} on lines: {lines_with_tabs}")
