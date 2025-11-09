"""Event system for publish-subscribe architecture."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import logging

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events in the system."""

    PARSING = "parsing"
    PATH_PROCESSING = "path_processing"
    POINT_PROCESSING = "point_processing"
    CURVE_PROCESSING = "curve_processing"
    OUTPUT_GENERATION = "output_generation"
    ERROR = "error"
    VALIDATION = "validation"
    PROGRESS = "progress"


@dataclass
class Event:
    """Base event class."""

    event_type: EventType
    timestamp: float
    data: Dict[str, Any]
    source: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate event after initialization."""
        if not isinstance(self.event_type, EventType):
            raise ValueError(f"Invalid event type: {self.event_type}")


@dataclass
class ParsingEvent(Event):
    """Event for file parsing operations."""

    def __init__(self, action: str, file_path: Union[str, Path], **kwargs):
        import time

        super().__init__(
            event_type=EventType.PARSING,
            timestamp=time.time(),
            data={"action": action, "file_path": str(file_path), **kwargs},
            source="parser",
        )


@dataclass
class PathEvent(Event):
    """Event for path processing operations."""

    def __init__(self, action: str, path_id: str, **kwargs):
        import time

        super().__init__(
            event_type=EventType.PATH_PROCESSING,
            timestamp=time.time(),
            data={"action": action, "path_id": path_id, **kwargs},
            source="path_processor",
        )


@dataclass
class PointEvent(Event):
    """Event for point processing operations."""

    def __init__(self, action: str, point_data: Dict[str, Any], **kwargs):
        import time

        super().__init__(
            event_type=EventType.POINT_PROCESSING,
            timestamp=time.time(),
            data={"action": action, "point_data": point_data, **kwargs},
            source="point_processor",
        )


@dataclass
class CurveEvent(Event):
    """Event for curve processing operations."""

    def __init__(self, action: str, curve_type: str, **kwargs):
        import time

        super().__init__(
            event_type=EventType.CURVE_PROCESSING,
            timestamp=time.time(),
            data={"action": action, "curve_type": curve_type, **kwargs},
            source="curve_processor",
        )


@dataclass
class OutputEvent(Event):
    """Event for output generation operations."""

    def __init__(
        self, action: str, output_type: str, file_path: Union[str, Path], **kwargs
    ):
        import time

        super().__init__(
            event_type=EventType.OUTPUT_GENERATION,
            timestamp=time.time(),
            data={
                "action": action,
                "output_type": output_type,
                "file_path": str(file_path),
                **kwargs,
            },
            source="output_generator",
        )


@dataclass
class ErrorEvent(Event):
    """Event for error conditions."""

    def __init__(self, error_type: str, message: str, **kwargs):
        import time

        super().__init__(
            event_type=EventType.ERROR,
            timestamp=time.time(),
            data={"error_type": error_type, "message": message, **kwargs},
            source="error_handler",
        )


@dataclass
class ValidationEvent(Event):
    """Event for validation operations."""

    def __init__(self, action: str, validation_type: str, result: bool, **kwargs):
        import time

        super().__init__(
            event_type=EventType.VALIDATION,
            timestamp=time.time(),
            data={
                "action": action,
                "validation_type": validation_type,
                "result": result,
                **kwargs,
            },
            source="validator",
        )


@dataclass
class ProgressEvent(Event):
    """Event for progress tracking."""

    def __init__(
        self, stage: str, progress: float, total: Optional[float] = None, **kwargs
    ):
        import time

        super().__init__(
            event_type=EventType.PROGRESS,
            timestamp=time.time(),
            data={"stage": stage, "progress": progress, "total": total, **kwargs},
            source="progress_tracker",
        )


class EventSubscriber(ABC):
    """Abstract base class for event subscribers."""

    @abstractmethod
    def handle_event(self, event: Event) -> None:
        """Handle an event."""
        pass

    @abstractmethod
    def get_subscribed_events(self) -> List[EventType]:
        """Get list of event types this subscriber handles."""
        pass


class EventPublisher:
    """Central event publisher for the publish-subscribe system."""

    def __init__(self):
        """Initialize the event publisher."""
        self._subscribers: Dict[EventType, List[EventSubscriber]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000

    def subscribe(self, subscriber: EventSubscriber) -> None:
        """Subscribe to events."""
        for event_type in subscriber.get_subscribed_events():
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if subscriber not in self._subscribers[event_type]:
                self._subscribers[event_type].append(subscriber)
                logger.debug(
                    f"Subscribed {subscriber.__class__.__name__} to {event_type}"
                )

    def unsubscribe(self, subscriber: EventSubscriber) -> None:
        """Unsubscribe from events."""
        for event_type in subscriber.get_subscribed_events():
            if event_type in self._subscribers:
                if subscriber in self._subscribers[event_type]:
                    self._subscribers[event_type].remove(subscriber)
                    logger.debug(
                        f"Unsubscribed {subscriber.__class__.__name__} from {event_type}"
                    )

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        # Add to history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        # Notify subscribers
        if event.event_type in self._subscribers:
            for subscriber in self._subscribers[event.event_type]:
                try:
                    subscriber.handle_event(event)
                except Exception as e:
                    logger.error(
                        f"Error in subscriber {subscriber.__class__.__name__}: {e}"
                    )

    def get_event_history(self) -> List[Event]:
        """Get event history."""
        return self._event_history.copy()

    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()

    def get_subscribers(self, event_type: EventType) -> List[EventSubscriber]:
        """Get subscribers for an event type."""
        return self._subscribers.get(event_type, []).copy()


# Global event publisher instance
_event_publisher: Optional[EventPublisher] = None


def get_event_publisher() -> EventPublisher:
    """Get the global event publisher instance."""
    global _event_publisher
    if _event_publisher is None:
        _event_publisher = EventPublisher()
    return _event_publisher


def publish_event(event: Event) -> None:
    """Publish an event using the global publisher."""
    get_event_publisher().publish(event)


def subscribe_to_events(subscriber: EventSubscriber) -> None:
    """Subscribe to events using the global publisher."""
    get_event_publisher().subscribe(subscriber)


def unsubscribe_from_events(subscriber: EventSubscriber) -> None:
    """Unsubscribe from events using the global publisher."""
    get_event_publisher().unsubscribe(subscriber)


def reset_event_system() -> None:
    """Reset the event system (for testing)."""
    global _event_publisher
    _event_publisher = None


# Convenience aliases
event_publisher = get_event_publisher
