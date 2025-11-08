"""Event system for the SVG processing pipeline."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from pathlib import Path

from .models import WeldPath, WeldPoint


class EventType(Enum):
    """Types of events in the processing pipeline."""

    # Parsing events
    PARSING_STARTED = "parsing_started"
    PARSING_PROGRESS = "parsing_progress"
    PARSING_COMPLETED = "parsing_completed"

    # Path events
    PATH_STARTED = "path_started"
    PATH_COMPLETED = "path_completed"

    # Point events
    POINT_GENERATED = "point_generated"
    POINTS_BATCH = "points_batch"

    # Curve events
    CURVE_APPROXIMATED = "curve_approximated"

    # Processing events
    PROCESSING_STARTED = "processing_started"
    PROCESSING_PROGRESS = "processing_progress"
    PROCESSING_COMPLETED = "processing_completed"

    # Output events
    OUTPUT_STARTED = "output_started"
    OUTPUT_PROGRESS = "output_progress"
    OUTPUT_COMPLETED = "output_completed"

    # Error events
    ERROR_OCCURRED = "error_occurred"
    WARNING_ISSUED = "warning_issued"


@dataclass
class Event:
    """Base event class."""

    event_type: EventType
    timestamp: float
    data: Dict[str, Any]
    source: Optional[str] = None

    def __post_init__(self):
        """Set timestamp if not provided."""
        if not hasattr(self, "timestamp") or self.timestamp is None:
            import time

            self.timestamp = time.time()


@dataclass
class ParsingEvent(Event):
    """Event for parsing operations."""

    svg_path: Optional[Path] = None
    total_elements: Optional[int] = None
    processed_elements: Optional[int] = None
    current_element: Optional[str] = None


@dataclass
class PathEvent(Event):
    """Event for path processing."""

    path: Optional[WeldPath] = None
    path_index: Optional[int] = None
    total_paths: Optional[int] = None


@dataclass
class PointEvent(Event):
    """Event for point generation."""

    point: Optional[WeldPoint] = None
    points: Optional[List[WeldPoint]] = None
    path_id: Optional[str] = None
    point_index: Optional[int] = None
    total_points: Optional[int] = None


@dataclass
class CurveEvent(Event):
    """Event for curve approximation."""

    curve_type: Optional[str] = None
    original_command: Optional[str] = None
    approximated_points: Optional[List[WeldPoint]] = None
    control_points: Optional[List[tuple]] = None


@dataclass
class OutputEvent(Event):
    """Event for output generation."""

    output_type: Optional[str] = None  # 'gcode', 'animation', 'png'
    output_path: Optional[Path] = None
    progress: Optional[float] = None  # 0.0 to 1.0
    total_size: Optional[int] = None
    current_size: Optional[int] = None


class ErrorEvent(Event):
    """Event for errors and warnings."""

    def __init__(
        self,
        event_type: EventType,
        timestamp: float,
        data: Dict[str, Any],
        message: str,
        source: Optional[str] = None,
        exception: Optional[Exception] = None,
        severity: str = "error",
    ):
        super().__init__(event_type, timestamp, data, source)
        self.message = message
        self.exception = exception
        self.severity = severity


class EventSubscriber(ABC):
    """Abstract base class for event subscribers."""

    @abstractmethod
    def handle_event(self, event: Event) -> None:
        """Handle an event."""
        pass

    @abstractmethod
    def get_subscribed_events(self) -> Set[EventType]:
        """Get the set of event types this subscriber is interested in."""
        pass


class EventPublisher:
    """Event publisher that manages subscribers and publishes events."""

    def __init__(self):
        """Initialize the event publisher."""
        self._subscribers: Dict[EventType, List[EventSubscriber]] = {}
        self._global_subscribers: List[EventSubscriber] = []
        self._event_history: List[Event] = []
        self._max_history = 1000

    def subscribe(
        self, subscriber: EventSubscriber, event_types: Optional[Set[EventType]] = None
    ) -> None:
        """Subscribe to specific event types or all events.

        Args:
            subscriber: The subscriber to register
            event_types: Specific event types to subscribe to, or None for all events
        """
        if event_types is None:
            # Subscribe to all events
            self._global_subscribers.append(subscriber)
        else:
            # Subscribe to specific event types
            for event_type in event_types:
                if event_type not in self._subscribers:
                    self._subscribers[event_type] = []
                self._subscribers[event_type].append(subscriber)

    def unsubscribe(
        self, subscriber: EventSubscriber, event_types: Optional[Set[EventType]] = None
    ) -> None:
        """Unsubscribe from specific event types or all events."""
        if event_types is None:
            # Unsubscribe from all events
            if subscriber in self._global_subscribers:
                self._global_subscribers.remove(subscriber)
            # Also remove from specific subscriptions
            for subscribers_list in self._subscribers.values():
                if subscriber in subscribers_list:
                    subscribers_list.remove(subscriber)
        else:
            # Unsubscribe from specific event types
            for event_type in event_types:
                if (
                    event_type in self._subscribers
                    and subscriber in self._subscribers[event_type]
                ):
                    self._subscribers[event_type].remove(subscriber)

    def publish(self, event: Event) -> None:
        """Publish an event to all relevant subscribers."""
        # Add to history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        # Notify global subscribers
        for subscriber in self._global_subscribers:
            try:
                subscriber.handle_event(event)
            except Exception as e:
                # Don't let subscriber errors break the publisher
                print(f"Error in subscriber {subscriber.__class__.__name__}: {e}")

        # Notify specific subscribers
        if event.event_type in self._subscribers:
            for subscriber in self._subscribers[event.event_type]:
                try:
                    subscriber.handle_event(event)
                except Exception as e:
                    print(f"Error in subscriber {subscriber.__class__.__name__}: {e}")

    def get_event_history(self, event_type: Optional[EventType] = None) -> List[Event]:
        """Get event history, optionally filtered by event type."""
        if event_type is None:
            return self._event_history.copy()
        return [
            event for event in self._event_history if event.event_type == event_type
        ]

    def clear_history(self) -> None:
        """Clear the event history."""
        self._event_history.clear()


# Global event publisher instance
event_publisher = EventPublisher()


def publish_event(event: Event) -> None:
    """Convenience function to publish an event."""
    event_publisher.publish(event)


def subscribe_to_events(
    subscriber: EventSubscriber, event_types: Optional[Set[EventType]] = None
) -> None:
    """Convenience function to subscribe to events."""
    event_publisher.subscribe(subscriber, event_types)


def unsubscribe_from_events(
    subscriber: EventSubscriber, event_types: Optional[Set[EventType]] = None
) -> None:
    """Convenience function to unsubscribe from events."""
    event_publisher.unsubscribe(subscriber, event_types)
