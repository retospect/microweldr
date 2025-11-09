"""Event-driven file processor with factory pattern."""

from pathlib import Path
from typing import Dict, List, Optional, Type, Union
import logging

from .processing_events import FileReaderPublisher, EventType, ProcessingEvent
from .enhanced_readers import EnhancedSVGReader, EnhancedDXFReader
from .enhanced_writers import GCodeWriterSubscriber, AnimationWriterSubscriber
from .error_handling import FileProcessingError, handle_errors

logger = logging.getLogger(__name__)


class EventDrivenProcessor:
    """Main processor using event-driven architecture."""

    def __init__(self, config):
        self.config = config
        self._readers: Dict[str, Type[FileReaderPublisher]] = {}
        self._writers: Dict[str, Type] = {}
        self._setup_readers_and_writers()

    def _setup_readers_and_writers(self):
        """Register available readers and writers."""
        # Register readers by file extension
        self._readers[".svg"] = EnhancedSVGReader
        self._readers[".dxf"] = EnhancedDXFReader

        # Register writers by file extension
        self._writers[".gcode"] = GCodeWriterSubscriber
        self._writers[".g"] = GCodeWriterSubscriber
        self._writers[".nc"] = GCodeWriterSubscriber
        self._writers[".svg"] = AnimationWriterSubscriber
        self._writers[".png"] = AnimationWriterSubscriber

    def _create_reader(self, file_path: Path) -> Optional[FileReaderPublisher]:
        """Create appropriate reader for the file."""
        extension = file_path.suffix.lower()

        if extension not in self._readers:
            logger.error(f"No reader available for extension: {extension}")
            return None

        reader_class = self._readers[extension]
        logger.info(f"Creating {reader_class.__name__} for {file_path}")

        return reader_class()

    def _create_writer(self, file_path: Path):
        """Create appropriate writer for the file."""
        extension = file_path.suffix.lower()

        if extension not in self._writers:
            logger.error(f"No writer available for extension: {extension}")
            return None

        writer_class = self._writers[extension]
        logger.info(f"Creating {writer_class.__name__} for {file_path}")

        return writer_class(self.config)

    @handle_errors(default_error=FileProcessingError)
    def process_file(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        animation_path: Optional[Union[str, Path]] = None,
        **kwargs,
    ) -> bool:
        """Process input file using event-driven architecture."""
        input_path = Path(input_path)
        output_path = Path(output_path)

        logger.info(f"Processing: {input_path} → {output_path}")

        # Validate input file
        if not input_path.exists():
            raise FileProcessingError(f"Input file not found: {input_path}")

        # Create reader based on input file extension
        reader = self._create_reader(input_path)
        if not reader:
            raise FileProcessingError(
                f"Unsupported input file type: {input_path.suffix}"
            )

        # Create primary output writer
        primary_writer = self._create_writer(output_path)
        if not primary_writer:
            raise FileProcessingError(
                f"Unsupported output file type: {output_path.suffix}"
            )

        # Create animation writer if requested
        animation_writer = None
        if animation_path:
            animation_path = Path(animation_path)
            animation_writer = self._create_writer(animation_path)
            if not animation_writer:
                logger.warning(
                    f"Cannot create animation writer for: {animation_path.suffix}"
                )

        # Subscribe writers to reader events
        reader.subscribe(primary_writer)
        if animation_writer:
            reader.subscribe(animation_writer)

        # Process the file (this will emit events)
        logger.info(f"Reading {input_path.suffix.upper()} file...")
        weld_paths = reader.process_file(input_path)

        if not weld_paths:
            raise FileProcessingError("No weld paths found in input file")

        logger.info(f"Found {len(weld_paths)} weld paths")

        # Write primary output
        success = primary_writer.write_file(output_path, **kwargs)

        # Write animation if requested
        if animation_writer:
            try:
                animation_writer.write_file(animation_path, **kwargs)
            except Exception as e:
                logger.warning(f"Failed to write animation: {e}")
                # Don't fail the whole process if animation fails

        return success

    def get_supported_input_extensions(self) -> List[str]:
        """Get supported input file extensions."""
        return list(self._readers.keys())

    def get_supported_output_extensions(self) -> List[str]:
        """Get supported output file extensions."""
        return list(self._writers.keys())
