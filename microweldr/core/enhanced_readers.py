"""Enhanced file readers using event-driven architecture."""

from pathlib import Path
from typing import List
import logging

from .processing_events import FileReaderPublisher
from .data_models import WeldPath
from .dxf_reader import DXFReader as BaseDXFReader
from .svg_reader import SVGReader as BaseSVGReader

logger = logging.getLogger(__name__)


class EnhancedSVGReader(FileReaderPublisher):
    """SVG reader that publishes processing events."""

    def __init__(self):
        super().__init__()
        self._base_reader = BaseSVGReader()

    def can_read_file(self, file_path: Path) -> bool:
        """Check if this reader can handle SVG files."""
        return file_path.suffix.lower() == ".svg"

    def read_file(self, file_path: Path) -> List[WeldPath]:
        """Read SVG file and return weld paths."""
        logger.info(f"Reading SVG file: {file_path}")
        return self._base_reader.parse_file(file_path)


class EnhancedDXFReader(FileReaderPublisher):
    """DXF reader that publishes processing events."""

    def __init__(self):
        super().__init__()
        self._base_reader = BaseDXFReader()

    def can_read_file(self, file_path: Path) -> bool:
        """Check if this reader can handle DXF files."""
        return file_path.suffix.lower() == ".dxf"

    def read_file(self, file_path: Path) -> List[WeldPath]:
        """Read DXF file and return weld paths."""
        logger.info(f"Reading DXF file: {file_path}")
        return self._base_reader.parse_file(file_path)
