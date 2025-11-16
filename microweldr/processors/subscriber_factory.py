"""Subscriber factory for centralized subscriber creation and management."""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Type
from dataclasses import dataclass

from ..core.events import EventSubscriber
from ..core.config import Config

logger = logging.getLogger(__name__)


@dataclass
class SubscriberConfig:
    """Configuration for a subscriber."""

    subscriber_type: str
    priority: int
    enabled: bool = True
    parameters: Dict[str, Any] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


class SubscriberFactory:
    """Factory for creating and managing subscribers with priority ordering."""

    def __init__(self, config: Config):
        """Initialize subscriber factory."""
        self.config = config
        self.registered_types: Dict[str, Type[EventSubscriber]] = {}
        self.active_subscribers: List[EventSubscriber] = []
        self._register_builtin_subscribers()

    def _register_builtin_subscribers(self):
        """Register built-in subscriber types."""
        # Import here to avoid circular imports
        from .subscribers import (
            ProgressTracker,
            LoggingSubscriber,
            StatisticsSubscriber,
            ValidationSubscriber,
        )
        from .bounding_box_subscriber import BoundingBoxSubscriber
        from .streaming_gcode_subscriber import StreamingGCodeSubscriber
        from .streaming_animation_subscriber import StreamingAnimationSubscriber

        self.registered_types.update(
            {
                "progress": ProgressTracker,
                "logging": LoggingSubscriber,
                "statistics": StatisticsSubscriber,
                "validation": ValidationSubscriber,
                "bounding_box": BoundingBoxSubscriber,
                "gcode": StreamingGCodeSubscriber,
                "animation": StreamingAnimationSubscriber,
            }
        )

    def register_subscriber_type(
        self, name: str, subscriber_class: Type[EventSubscriber]
    ):
        """Register a new subscriber type."""
        self.registered_types[name] = subscriber_class
        logger.debug(f"Registered subscriber type: {name}")

    def create_processing_subscribers(
        self,
        output_path: Path,
        animation_path: Optional[Path] = None,
        png_path: Optional[Path] = None,
        verbose: bool = False,
    ) -> List[EventSubscriber]:
        """Create subscribers for a processing session with proper priority ordering."""

        # Define subscriber configurations with priorities
        subscriber_configs = [
            # Core subscribers (always enabled)
            SubscriberConfig("validation", priority=0),  # Highest priority
            SubscriberConfig("bounding_box", priority=10),
            SubscriberConfig("statistics", priority=15),
            # Output subscribers
            SubscriberConfig(
                "gcode", priority=20, parameters={"output_path": output_path}
            ),
        ]

        # Add optional subscribers
        if animation_path:
            subscriber_configs.append(
                SubscriberConfig(
                    "animation", priority=25, parameters={"output_path": animation_path}
                )
            )

        if png_path:
            subscriber_configs.append(
                SubscriberConfig(
                    "animation", priority=25, parameters={"output_path": png_path}
                )
            )

        # Add utility subscribers
        subscriber_configs.append(
            SubscriberConfig("progress", priority=30, parameters={"verbose": verbose})
        )

        if verbose:
            subscriber_configs.append(
                SubscriberConfig(
                    "logging", priority=35, parameters={"level": logging.DEBUG}
                )
            )

        # Create and register subscribers in priority order
        subscribers = self._create_subscribers_from_configs(subscriber_configs)

        # Sort by priority (lower number = higher priority)
        subscribers.sort(key=lambda s: getattr(s, "get_priority", lambda: 999)())

        # Register all subscribers
        for subscriber in subscribers:
            subscribe_to_events(subscriber)
            self.active_subscribers.append(subscriber)

        logger.info(f"Created {len(subscribers)} subscribers for processing")
        return subscribers

    def _create_subscribers_from_configs(
        self, configs: List[SubscriberConfig]
    ) -> List[EventSubscriber]:
        """Create subscriber instances from configurations."""
        subscribers = []

        for config in configs:
            if not config.enabled:
                continue

            if config.subscriber_type not in self.registered_types:
                logger.warning(f"Unknown subscriber type: {config.subscriber_type}")
                continue

            try:
                subscriber = self._create_subscriber(config)
                if subscriber:
                    subscribers.append(subscriber)
            except Exception as e:
                logger.error(
                    f"Failed to create subscriber {config.subscriber_type}: {e}"
                )

        return subscribers

    def _create_subscriber(self, config: SubscriberConfig) -> Optional[EventSubscriber]:
        """Create a single subscriber instance."""
        subscriber_class = self.registered_types[config.subscriber_type]

        # Handle different constructor patterns
        if config.subscriber_type in ["gcode", "animation"]:
            # Subscribers that need output path and config
            output_path = config.parameters.get("output_path")
            if not output_path:
                logger.error(
                    f"Missing output_path for {config.subscriber_type} subscriber"
                )
                return None
            return subscriber_class(output_path, self.config)

        elif config.subscriber_type == "progress":
            # Progress tracker with verbose flag
            verbose = config.parameters.get("verbose", False)
            return subscriber_class(verbose=verbose)

        elif config.subscriber_type == "logging":
            # Logging subscriber with level
            level = config.parameters.get("level", logging.INFO)
            return subscriber_class(level)

        else:
            # Subscribers with no parameters
            return subscriber_class()

    def create_global_subscribers(self, verbose: bool = False) -> List[EventSubscriber]:
        """Create global subscribers that persist across processing sessions."""
        configs = [
            SubscriberConfig("validation", priority=0),
            SubscriberConfig("statistics", priority=15),
        ]

        if verbose:
            configs.append(
                SubscriberConfig("progress", priority=30, parameters={"verbose": True})
            )

        subscribers = self._create_subscribers_from_configs(configs)

        # Register global subscribers
        for subscriber in subscribers:
            subscribe_to_events(subscriber)
            self.active_subscribers.append(subscriber)

        return subscribers

    def cleanup_session_subscribers(self, session_subscribers: List[EventSubscriber]):
        """Clean up subscribers from a processing session."""
        for subscriber in session_subscribers:
            try:
                unsubscribe_from_events(subscriber)
                if subscriber in self.active_subscribers:
                    self.active_subscribers.remove(subscriber)
            except Exception as e:
                logger.warning(f"Error cleaning up subscriber {subscriber}: {e}")

    def cleanup_all_subscribers(self):
        """Clean up all active subscribers."""
        for subscriber in self.active_subscribers.copy():
            try:
                unsubscribe_from_events(subscriber)
            except Exception as e:
                logger.warning(f"Error cleaning up subscriber {subscriber}: {e}")

        self.active_subscribers.clear()

    def get_active_subscribers(self) -> List[EventSubscriber]:
        """Get list of currently active subscribers."""
        return self.active_subscribers.copy()

    def get_subscriber_by_type(self, subscriber_type: str) -> Optional[EventSubscriber]:
        """Get active subscriber by type."""
        target_class = self.registered_types.get(subscriber_type)
        if not target_class:
            return None

        for subscriber in self.active_subscribers:
            if isinstance(subscriber, target_class):
                return subscriber

        return None

    def get_validation_subscriber(self):
        """Get the validation subscriber (convenience method)."""
        return self.get_subscriber_by_type("validation")

    def get_statistics_subscriber(self):
        """Get the statistics subscriber (convenience method)."""
        return self.get_subscriber_by_type("statistics")

    def get_bounding_box_subscriber(self):
        """Get the bounding box subscriber (convenience method)."""
        return self.get_subscriber_by_type("bounding_box")


def create_subscriber_factory(config: Config) -> SubscriberFactory:
    """Create a subscriber factory instance."""
    return SubscriberFactory(config)
