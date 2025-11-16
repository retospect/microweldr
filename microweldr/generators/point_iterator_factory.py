"""Factory for creating appropriate point iterators based on file type."""

import logging
from pathlib import Path
from typing import Iterator, Dict, Any, Union, Protocol

from .svg_point_iterator import SVGPointIterator
from .dxf_point_iterator import DXFPointIterator

logger = logging.getLogger(__name__)


class PointIterator(Protocol):
    """Protocol for point iterators."""

    def iterate_points(self, file_path: Path) -> Iterator[Dict[str, Any]]:
        """Iterate through points in a file."""
        ...

    def count_points(self, file_path: Path) -> int:
        """Count total points in a file."""
        ...

    @staticmethod
    def supports_file(file_path: Path) -> bool:
        """Check if this iterator supports the given file type."""
        ...


class PointIteratorFactory:
    """Factory for creating point iterators based on file type."""

    _iterators = [
        SVGPointIterator,
        DXFPointIterator,
    ]

    @classmethod
    def create_iterator(cls, file_path: Union[str, Path], config=None) -> PointIterator:
        """Create appropriate point iterator for the given file.

        Args:
            file_path: Path to the file
            config: Configuration object to get dot_spacing from

        Returns:
            Point iterator instance for the file type

        Raises:
            ValueError: If no iterator supports the file type
        """
        file_path = Path(file_path)

        # Get dot_spacing from config, fallback to 2.0mm
        dot_spacing = 2.0  # Default fallback
        if config:
            try:
                dot_spacing = config.get("normal_welds", "dot_spacing", 2.0)
            except Exception:
                dot_spacing = 2.0

        for iterator_class in cls._iterators:
            if iterator_class.supports_file(file_path):
                logger.debug(
                    f"Using {iterator_class.__name__} for {file_path} with {dot_spacing}mm spacing"
                )
                # Pass dot_spacing to iterators that support it
                if iterator_class.__name__ == "DXFPointIterator":
                    return iterator_class(dot_spacing=dot_spacing)
                elif iterator_class.__name__ == "SVGPointIterator":
                    return iterator_class(dot_spacing=dot_spacing)
                else:
                    return iterator_class()

        raise ValueError(f"Unsupported file format: {file_path.suffix}")

    @classmethod
    def get_supported_extensions(cls) -> list[str]:
        """Get list of all supported file extensions.

        Returns:
            List of supported file extensions (e.g., ['.svg', '.dxf'])
        """
        extensions = []
        for iterator_class in cls._iterators:
            if hasattr(iterator_class, "SUPPORTED_EXTENSIONS"):
                extensions.extend(iterator_class.SUPPORTED_EXTENSIONS)

        return list(set(extensions))  # Remove duplicates


def iterate_points_from_file(
    file_path: Union[str, Path], config=None
) -> Iterator[Dict[str, Any]]:
    """
    Iterator that yields points from DXF/SVG files.

    This is used in both Phase 1 (analysis) and Phase 2 (generation)
    to avoid loading all points into memory at once.

    Args:
        file_path: Path to the file to process
        config: Configuration object to get dot_spacing from

    Yields:
        Dict containing point data with keys:
        - x, y: Point coordinates
        - weld_type: Type of weld ('normal', 'frangible', etc.)
        - path_id: Identifier for the path this point belongs to
        - custom_*: Any custom attributes (nozzle_temp, bed_temp, weld_height)

    Raises:
        ValueError: If file format is not supported
        Exception: If file parsing fails
    """
    file_path = Path(file_path)
    iterator = PointIteratorFactory.create_iterator(file_path, config=config)
    yield from iterator.iterate_points(file_path)


def count_points_in_file(file_path: Union[str, Path], config=None) -> int:
    """Count total points in a file without storing them.

    Args:
        file_path: Path to the file
        config: Configuration object to get dot_spacing from

    Returns:
        Total number of points in the file
    """
    return sum(1 for _ in iterate_points_from_file(file_path, config=config))
