"""Factory pattern for file readers and writers with publisher-subscriber architecture."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Type, Union
import logging

from .data_models import WeldPath
from .error_handling import FileProcessingError, handle_errors
from .file_readers import FileReaderPublisher
from .svg_reader import SVGReader
from .dxf_reader import DXFReader

logger = logging.getLogger(__name__)


class FileWriterSubscriber(ABC):
    """Abstract base class for file writers that subscribe to file readers."""

    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """Get list of supported file extensions."""
        pass

    @abstractmethod
    def can_write_file(self, file_path: Path) -> bool:
        """Check if this writer can handle the given file."""
        pass

    @abstractmethod
    def write_file(
        self, weld_paths: List[WeldPath], output_path: Path, **kwargs
    ) -> bool:
        """Write weld paths to file."""
        pass


class GCodeWriter(FileWriterSubscriber):
    """G-code file writer."""

    def __init__(self, config):
        self.config = config

    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return [".gcode", ".g", ".nc"]

    def can_write_file(self, file_path: Path) -> bool:
        """Check if this writer can handle the given file."""
        return file_path.suffix.lower() in self.get_supported_extensions()

    @handle_errors(default_error=FileProcessingError)
    def write_file(
        self, weld_paths: List[WeldPath], output_path: Path, **kwargs
    ) -> bool:
        """Write weld paths to G-code file."""
        logger.info(f"Writing G-code to: {output_path}")

        # Use streaming G-code subscriber for modern architecture
        from ..outputs.streaming_gcode_subscriber import StreamingGCodeSubscriber
        from ..core.events import Event, EventType

        subscriber = StreamingGCodeSubscriber(output_path, self.config)

        # Convert WeldPaths to events for compatibility
        for path in weld_paths:
            # Path start event
            path_event = Event(
                event_type=EventType.PATH_PROCESSING,
                data={
                    "action": "path_start",
                    "path_data": {"id": path.svg_id, "weld_type": path.weld_type},
                },
            )
            subscriber.handle_event(path_event)

            # Point events
            for point in path.points:
                point_event = Event(
                    event_type=EventType.POINT_PROCESSING,
                    data={
                        "action": "point_processed",
                        "x": point.x,
                        "y": point.y,
                        "weld_type": point.weld_type,
                    },
                )
                subscriber.handle_event(point_event)

            # Path end event
            path_end_event = Event(
                event_type=EventType.PATH_PROCESSING, data={"action": "path_end"}
            )
            subscriber.handle_event(path_end_event)

        # Finalize
        finalize_event = Event(
            event_type=EventType.OUTPUT_GENERATION,
            data={"action": "processing_complete"},
        )
        subscriber.handle_event(finalize_event)

        logger.info(f"G-code written successfully: {output_path}")
        return True


class AnimationWriter(FileWriterSubscriber):
    """Animation file writer (SVG/PNG)."""

    def __init__(self, config):
        self.config = config

    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return [".svg", ".png"]

    def can_write_file(self, file_path: Path) -> bool:
        """Check if this writer can handle the given file."""
        return file_path.suffix.lower() in self.get_supported_extensions()

    @handle_errors(default_error=FileProcessingError)
    def write_file(
        self, weld_paths: List[WeldPath], output_path: Path, **kwargs
    ) -> bool:
        """Write weld paths to animation file."""
        from ..animation.generator import AnimationGenerator

        logger.info(f"Writing animation to: {output_path}")

        generator = AnimationGenerator(self.config)

        # Determine format from extension
        is_png = output_path.suffix.lower() == ".png"

        generator.generate_animation(
            weld_paths, str(output_path), format="png" if is_png else "svg"
        )

        logger.info(f"Animation written successfully: {output_path}")
        return True


class FileReaderFactory:
    """Factory for creating file readers based on file extension."""

    _readers: Dict[str, Type[FileReaderPublisher]] = {}

    @classmethod
    def register_reader(
        cls, extensions: List[str], reader_class: Type[FileReaderPublisher]
    ):
        """Register a reader class for given file extensions."""
        for ext in extensions:
            cls._readers[ext.lower()] = reader_class

    @classmethod
    def create_reader(cls, file_path: Path) -> Optional[FileReaderPublisher]:
        """Create appropriate reader for the given file."""
        extension = file_path.suffix.lower()

        if extension not in cls._readers:
            logger.error(f"No reader available for extension: {extension}")
            return None

        reader_class = cls._readers[extension]
        logger.info(f"Creating {reader_class.__name__} for {file_path}")

        return reader_class()

    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """Get all supported file extensions."""
        return list(cls._readers.keys())


class FileWriterFactory:
    """Factory for creating file writers based on file extension."""

    _writers: Dict[str, Type[FileWriterSubscriber]] = {}

    @classmethod
    def register_writer(
        cls, extensions: List[str], writer_class: Type[FileWriterSubscriber]
    ):
        """Register a writer class for given file extensions."""
        for ext in extensions:
            cls._writers[ext.lower()] = writer_class

    @classmethod
    def create_writer(cls, file_path: Path, config) -> Optional[FileWriterSubscriber]:
        """Create appropriate writer for the given file."""
        extension = file_path.suffix.lower()

        if extension not in cls._writers:
            logger.error(f"No writer available for extension: {extension}")
            return None

        writer_class = cls._writers[extension]
        logger.info(f"Creating {writer_class.__name__} for {file_path}")

        return writer_class(config)

    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """Get all supported file extensions."""
        return list(cls._writers.keys())


class FileProcessor:
    """Main file processor that coordinates readers and writers."""

    def __init__(self, config):
        self.config = config
        self._setup_factories()

    def _setup_factories(self):
        """Register all available readers and writers."""
        # Register readers
        FileReaderFactory.register_reader([".svg"], SVGReader)
        FileReaderFactory.register_reader([".dxf"], DXFReader)

        # Register writers
        FileWriterFactory.register_writer([".gcode", ".g", ".nc"], GCodeWriter)
        FileWriterFactory.register_writer([".svg", ".png"], AnimationWriter)

    @handle_errors(default_error=FileProcessingError)
    def process_file(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        animation_path: Optional[Union[str, Path]] = None,
        **kwargs,
    ) -> bool:
        """Process input file and generate outputs."""
        input_path = Path(input_path)
        output_path = Path(output_path)

        logger.info(f"Processing: {input_path} → {output_path}")

        # Validate input file
        if not input_path.exists():
            raise FileProcessingError(f"Input file not found: {input_path}")

        # Create reader
        reader = FileReaderFactory.create_reader(input_path)
        if not reader:
            raise FileProcessingError(
                f"Unsupported input file type: {input_path.suffix}"
            )

        # Parse input file
        logger.info(f"Reading {input_path.suffix.upper()} file...")
        weld_paths = reader.parse_file(input_path)

        if not weld_paths:
            raise FileProcessingError("No weld paths found in input file")

        logger.info(f"Found {len(weld_paths)} weld paths")

        # Create and use primary output writer
        writer = FileWriterFactory.create_writer(output_path, self.config)
        if not writer:
            raise FileProcessingError(
                f"Unsupported output file type: {output_path.suffix}"
            )

        success = writer.write_file(weld_paths, output_path, **kwargs)

        # Generate animation if requested
        if animation_path:
            animation_path = Path(animation_path)
            animation_writer = FileWriterFactory.create_writer(
                animation_path, self.config
            )

            if animation_writer:
                animation_writer.write_file(weld_paths, animation_path, **kwargs)
            else:
                logger.warning(
                    f"Cannot create animation writer for: {animation_path.suffix}"
                )

        return success

    def get_supported_input_extensions(self) -> List[str]:
        """Get supported input file extensions."""
        return FileReaderFactory.get_supported_extensions()

    def get_supported_output_extensions(self) -> List[str]:
        """Get supported output file extensions."""
        return FileWriterFactory.get_supported_extensions()


# Initialize factories on module import
def initialize_factories():
    """Initialize the factory system."""
    # This will be called when the module is imported
    pass


# Auto-initialize when module is imported
initialize_factories()
