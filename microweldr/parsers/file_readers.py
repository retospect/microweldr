"""Publisher-subscriber architecture for file readers."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Protocol, Set

from ..core.data_models import WeldPath, WeldType, ProcessingStats
from ..core.error_handling import FileProcessingError, handle_errors, error_context

logger = logging.getLogger(__name__)


class FileReaderSubscriber(Protocol):
    """Protocol for file reader subscribers."""

    def on_file_started(self, file_path: Path, file_type: str) -> None:
        """Called when file processing starts."""
        ...

    def on_path_found(self, path: WeldPath) -> None:
        """Called when a weld path is found."""
        ...

    def on_file_completed(
        self, file_path: Path, paths: List[WeldPath], stats: ProcessingStats
    ) -> None:
        """Called when file processing completes."""
        ...

    def on_error(self, file_path: Path, error: Exception) -> None:
        """Called when an error occurs."""
        ...


class FileReaderPublisher(ABC):
    """Abstract base class for file readers with publisher functionality."""

    def __init__(self):
        self._subscribers: Set[FileReaderSubscriber] = set()
        self.stats = ProcessingStats()

    def subscribe(self, subscriber: FileReaderSubscriber) -> None:
        """Add a subscriber."""
        self._subscribers.add(subscriber)
        logger.debug(
            f"Added subscriber {type(subscriber).__name__} to {type(self).__name__}"
        )

    def unsubscribe(self, subscriber: FileReaderSubscriber) -> None:
        """Remove a subscriber."""
        self._subscribers.discard(subscriber)
        logger.debug(
            f"Removed subscriber {type(subscriber).__name__} from {type(self).__name__}"
        )

    def _notify_file_started(self, file_path: Path, file_type: str) -> None:
        """Notify subscribers that file processing started."""
        for subscriber in self._subscribers:
            try:
                subscriber.on_file_started(file_path, file_type)
            except Exception as e:
                logger.error(
                    f"Error notifying subscriber {type(subscriber).__name__}: {e}"
                )

    def _notify_path_found(self, path: WeldPath) -> None:
        """Notify subscribers that a path was found."""
        for subscriber in self._subscribers:
            try:
                subscriber.on_path_found(path)
            except Exception as e:
                logger.error(
                    f"Error notifying subscriber {type(subscriber).__name__}: {e}"
                )

    def _notify_file_completed(
        self, file_path: Path, paths: List[WeldPath], stats: ProcessingStats
    ) -> None:
        """Notify subscribers that file processing completed."""
        for subscriber in self._subscribers:
            try:
                subscriber.on_file_completed(file_path, paths, stats)
            except Exception as e:
                logger.error(
                    f"Error notifying subscriber {type(subscriber).__name__}: {e}"
                )

    def _notify_error(self, file_path: Path, error: Exception) -> None:
        """Notify subscribers of an error."""
        for subscriber in self._subscribers:
            try:
                subscriber.on_error(file_path, error)
            except Exception as e:
                logger.error(
                    f"Error notifying subscriber {type(subscriber).__name__}: {e}"
                )

    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """Get list of supported file extensions."""
        pass

    @abstractmethod
    def can_read_file(self, file_path: Path) -> bool:
        """Check if this reader can handle the given file."""
        pass

    @abstractmethod
    def _parse_file_internal(self, file_path: Path) -> List[WeldPath]:
        """Internal method to parse the file. Must be implemented by subclasses."""
        pass

    @handle_errors(
        error_types={
            FileNotFoundError: FileProcessingError,
            PermissionError: FileProcessingError,
        },
        default_error=FileProcessingError,
    )
    def parse_file(self, file_path: Path) -> List[WeldPath]:
        """
        Parse a file and return weld paths.

        Args:
            file_path: Path to the file to parse

        Returns:
            List of weld paths found in the file

        Raises:
            FileProcessingError: If file cannot be processed
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileProcessingError(f"File not found: {file_path}")

        if not self.can_read_file(file_path):
            raise FileProcessingError(f"Unsupported file type: {file_path.suffix}")

        with error_context("file_parsing", file_path=str(file_path)):
            # Notify start
            self._notify_file_started(file_path, file_path.suffix.lower())

            try:
                # Parse the file
                paths = self._parse_file_internal(file_path)

                # Update statistics
                file_stats = ProcessingStats()
                file_stats.files_processed = 1
                file_stats.total_paths = len(paths)
                file_stats.total_points = sum(len(path.points) for path in paths)

                for path in paths:
                    if path.weld_type == WeldType.NORMAL:
                        file_stats.normal_welds += 1
                    elif path.weld_type == WeldType.FRANGIBLE:
                        file_stats.frangible_welds += 1

                # Notify each path found
                for path in paths:
                    self._notify_path_found(path)

                # Notify completion
                self._notify_file_completed(file_path, paths, file_stats)

                logger.info(
                    f"Successfully parsed {file_path}: {len(paths)} paths, {file_stats.total_points} points"
                )
                return paths

            except Exception as e:
                self._notify_error(file_path, e)
                raise


class MultiFileReader:
    """Manages multiple file readers and routes files to appropriate readers."""

    def __init__(self):
        self._readers: List[FileReaderPublisher] = []
        self._subscribers: Set[FileReaderSubscriber] = set()

    def register_reader(self, reader: FileReaderPublisher) -> None:
        """Register a file reader."""
        self._readers.append(reader)

        # Subscribe all current subscribers to the new reader
        for subscriber in self._subscribers:
            reader.subscribe(subscriber)

        logger.info(
            f"Registered reader {type(reader).__name__} for extensions: {reader.get_supported_extensions()}"
        )

    def subscribe(self, subscriber: FileReaderSubscriber) -> None:
        """Add a subscriber to all readers."""
        self._subscribers.add(subscriber)

        # Subscribe to all existing readers
        for reader in self._readers:
            reader.subscribe(subscriber)

    def unsubscribe(self, subscriber: FileReaderSubscriber) -> None:
        """Remove a subscriber from all readers."""
        self._subscribers.discard(subscriber)

        # Unsubscribe from all readers
        for reader in self._readers:
            reader.unsubscribe(subscriber)

    def get_reader_for_file(self, file_path: Path) -> Optional[FileReaderPublisher]:
        """Get the appropriate reader for a file."""
        for reader in self._readers:
            if reader.can_read_file(file_path):
                return reader
        return None

    def get_supported_extensions(self) -> List[str]:
        """Get all supported file extensions."""
        extensions = []
        for reader in self._readers:
            extensions.extend(reader.get_supported_extensions())
        return list(set(extensions))  # Remove duplicates

    def parse_file(self, file_path: Path) -> List[WeldPath]:
        """Parse a file using the appropriate reader."""
        reader = self.get_reader_for_file(file_path)
        if not reader:
            raise FileProcessingError(f"No reader available for file: {file_path}")

        return reader.parse_file(file_path)

    def parse_files(self, file_paths: List[Path]) -> List[WeldPath]:
        """Parse multiple files and combine results."""
        all_paths = []

        for file_path in file_paths:
            try:
                paths = self.parse_file(file_path)
                all_paths.extend(paths)
            except Exception as e:
                logger.error(f"Failed to parse {file_path}: {e}")
                # Continue with other files

        return all_paths


# Example subscriber implementations
class LoggingSubscriber:
    """Subscriber that logs file processing events."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def on_file_started(self, file_path: Path, file_type: str) -> None:
        if self.verbose:
            logger.info(f"Started processing {file_type} file: {file_path}")

    def on_path_found(self, path: WeldPath) -> None:
        if self.verbose:
            logger.debug(
                f"Found {path.weld_type.value} path with {len(path.points)} points"
            )

    def on_file_completed(
        self, file_path: Path, paths: List[WeldPath], stats: ProcessingStats
    ) -> None:
        logger.info(
            f"Completed {file_path}: {len(paths)} paths, {stats.total_points} points"
        )

    def on_error(self, file_path: Path, error: Exception) -> None:
        logger.error(f"Error processing {file_path}: {error}")


class StatsCollector:
    """Subscriber that collects processing statistics."""

    def __init__(self):
        self.total_stats = ProcessingStats()
        self.file_stats = {}

    def on_file_started(self, file_path: Path, file_type: str) -> None:
        pass

    def on_path_found(self, path: WeldPath) -> None:
        pass

    def on_file_completed(
        self, file_path: Path, paths: List[WeldPath], stats: ProcessingStats
    ) -> None:
        self.file_stats[str(file_path)] = stats

        # Update totals
        self.total_stats.files_processed += stats.files_processed
        self.total_stats.total_paths += stats.total_paths
        self.total_stats.total_points += stats.total_points
        self.total_stats.normal_welds += stats.normal_welds
        self.total_stats.frangible_welds += stats.frangible_welds
        self.total_stats.processing_time += stats.processing_time

    def on_error(self, file_path: Path, error: Exception) -> None:
        self.total_stats.errors.append(f"{file_path}: {error}")

    def get_summary(self) -> str:
        """Get a summary of processing statistics."""
        return (
            f"Processed {self.total_stats.files_processed} files, "
            f"{self.total_stats.total_paths} paths, "
            f"{self.total_stats.total_points} points "
            f"({self.total_stats.normal_welds} normal, {self.total_stats.frangible_welds} frangible)"
        )
