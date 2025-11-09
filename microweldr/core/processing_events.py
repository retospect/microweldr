"""Event system for file processing with publisher-subscriber pattern."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path

from .data_models import WeldPath


class EventType(Enum):
    """Types of processing events."""

    FILE_PARSED = "file_parsed"
    PATHS_EXTRACTED = "paths_extracted"
    PROCESSING_COMPLETE = "processing_complete"
    ERROR_OCCURRED = "error_occurred"


@dataclass
class ProcessingEvent:
    """Event emitted during file processing."""

    event_type: EventType
    source: str  # Name of the component that emitted the event
    data: Dict[str, Any]
    timestamp: Optional[float] = None


class EventSubscriber(ABC):
    """Abstract base class for event subscribers."""

    @abstractmethod
    def handle_event(self, event: ProcessingEvent) -> None:
        """Handle a processing event."""
        pass


class EventPublisher:
    """Publisher that emits events to subscribers."""

    def __init__(self):
        self._subscribers: List[EventSubscriber] = []

    def subscribe(self, subscriber: EventSubscriber) -> None:
        """Add a subscriber."""
        if subscriber not in self._subscribers:
            self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber: EventSubscriber) -> None:
        """Remove a subscriber."""
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    def publish(self, event: ProcessingEvent) -> None:
        """Publish an event to all subscribers."""
        for subscriber in self._subscribers:
            try:
                subscriber.handle_event(event)
            except Exception as e:
                # Log error but don't stop other subscribers
                print(f"Error in subscriber {type(subscriber).__name__}: {e}")


class FileReaderPublisher(EventPublisher):
    """Base class for file readers that publish events."""

    @abstractmethod
    def can_read_file(self, file_path: Path) -> bool:
        """Check if this reader can handle the file."""
        pass

    @abstractmethod
    def read_file(self, file_path: Path) -> List[WeldPath]:
        """Read file and return weld paths."""
        pass

    def process_file(self, file_path: Path) -> List[WeldPath]:
        """Process file and emit events."""
        # Emit file parsing event
        self.publish(
            ProcessingEvent(
                event_type=EventType.FILE_PARSED,
                source=self.__class__.__name__,
                data={"file_path": str(file_path), "file_type": file_path.suffix},
            )
        )

        # Read and parse file
        weld_paths = self.read_file(file_path)

        # Emit paths extracted event
        self.publish(
            ProcessingEvent(
                event_type=EventType.PATHS_EXTRACTED,
                source=self.__class__.__name__,
                data={
                    "weld_paths": weld_paths,
                    "path_count": len(weld_paths),
                    "file_path": str(file_path),
                },
            )
        )

        return weld_paths


class FileWriterSubscriber(EventSubscriber):
    """Base class for file writers that subscribe to events."""

    def __init__(self, config):
        self.config = config
        self._weld_paths: List[WeldPath] = []
        self._source_file: Optional[Path] = None

    @abstractmethod
    def can_write_file(self, file_path: Path) -> bool:
        """Check if this writer can handle the file."""
        pass

    @abstractmethod
    def write_output(self, output_path: Path, **kwargs) -> bool:
        """Write output file using stored weld paths."""
        pass

    def handle_event(self, event: ProcessingEvent) -> None:
        """Handle processing events."""
        if event.event_type == EventType.PATHS_EXTRACTED:
            self._weld_paths = event.data["weld_paths"]
            self._source_file = Path(event.data["file_path"])

    def write_file(self, output_path: Path, **kwargs) -> bool:
        """Write file using stored weld paths from events."""
        if not self._weld_paths:
            raise ValueError(
                "No weld paths available. Ensure reader has processed a file first."
            )

        return self.write_output(output_path, **kwargs)
