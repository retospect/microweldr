"""Event-driven processor for file conversion with publish-subscribe architecture."""

import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Union
import logging

from ..core.config import Config
from ..core.events import (
    Event,
    EventType,
    ParsingEvent,
    PathEvent,
    PointEvent,
    OutputEvent,
    ErrorEvent,
    ProgressEvent,
    EventSubscriber,
    publish_event,
    subscribe_to_events,
    unsubscribe_from_events,
)
from .subscriber_factory import SubscriberFactory
from .two_phase_processor import TwoPhaseProcessor
from ..generators.models import WeldPath, WeldPoint

logger = logging.getLogger(__name__)


class FileProcessingError(Exception):
    """Raised when file processing fails."""

    pass


class EventDrivenProcessor:
    """Event-driven processor for converting files with publish-subscribe architecture."""

    def __init__(
        self, config: Config, verbose: bool = False, use_two_phase: bool = True
    ):
        """Initialize the event-driven processor."""
        self.config = config
        self.verbose = verbose
        self.use_two_phase = use_two_phase

        if use_two_phase:
            # Use new two-phase architecture
            self.two_phase_processor = TwoPhaseProcessor(config, verbose)
            self.subscriber_factory = None
            self.global_subscribers = []
        else:
            # Use legacy event-driven architecture
            self.two_phase_processor = None
            self.subscriber_factory = SubscriberFactory(config)
            self.global_subscribers = self.subscriber_factory.create_global_subscribers(
                verbose
            )

    def __del__(self):
        """Clean up subscribers."""
        self.cleanup()

    def cleanup(self) -> None:
        """Clean up subscribers."""
        if self.subscriber_factory:
            self.subscriber_factory.cleanup_all_subscribers()

    def get_supported_input_extensions(self) -> List[str]:
        """Get supported input file extensions."""
        return [".svg", ".dxf"]

    def get_supported_output_types(self) -> List[str]:
        """Get supported output types."""
        return ["gcode", "animation", "png"]

    def process_file(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        animation_path: Optional[Union[str, Path]] = None,
        png_path: Optional[Union[str, Path]] = None,
        verbose: bool = False,
    ) -> bool:
        """Process input file and generate outputs."""
        input_path = Path(input_path)
        output_path = Path(output_path)

        if self.use_two_phase:
            # Use new two-phase architecture
            return self.two_phase_processor.process_file(
                input_path=input_path,
                output_path=output_path,
                animation_path=Path(animation_path) if animation_path else None,
                png_path=Path(png_path) if png_path else None,
                verbose=verbose,
            )

        # Legacy event-driven architecture
        try:
            # Publish start event
            publish_event(ParsingEvent("start", input_path))

            # Parse input file
            weld_paths = self._parse_input_file(input_path)

            if not weld_paths:
                publish_event(
                    ErrorEvent("parsing", f"No weld paths found in {input_path}")
                )
                return False

            # Publish parsing complete
            publish_event(
                ParsingEvent("complete", input_path, paths_count=len(weld_paths))
            )

            # Create processing subscribers using factory
            session_subscribers = self.subscriber_factory.create_processing_subscribers(
                output_path=output_path,
                animation_path=Path(animation_path) if animation_path else None,
                png_path=Path(png_path) if png_path else None,
                verbose=verbose,
            )

            try:
                # Process weld paths through events
                self._process_weld_paths_via_events(weld_paths)

                # Generate outputs
                publish_event(OutputEvent("generate", "gcode", output_path))

                if animation_path:
                    publish_event(OutputEvent("generate", "animation", animation_path))

                if png_path:
                    publish_event(OutputEvent("generate", "png", png_path))

                # Check for validation errors
                validation_subscriber = (
                    self.subscriber_factory.get_validation_subscriber()
                )
                if validation_subscriber:
                    validation_results = validation_subscriber.get_validation_results()
                    if validation_results["has_errors"]:
                        for error in validation_results["errors"]:
                            publish_event(ErrorEvent("validation", error))
                        return False

                return True

            finally:
                # Clean up session subscribers
                self.subscriber_factory.cleanup_session_subscribers(session_subscribers)

        except Exception as e:
            publish_event(ErrorEvent("processing", str(e)))
            if verbose:
                logger.exception("Error during file processing")
            raise FileProcessingError(f"Failed to process {input_path}: {e}")

    def _parse_input_file(self, input_path: Path) -> List[WeldPath]:
        """Parse input file based on extension."""
        extension = input_path.suffix.lower()

        if extension == ".svg":
            return self._parse_svg_file(input_path)
        elif extension == ".dxf":
            return self._parse_dxf_file(input_path)
        else:
            raise FileProcessingError(f"Unsupported file type: {extension}")

    def _parse_svg_file(self, svg_path: Path) -> List[WeldPath]:
        """Parse SVG file."""
        from .svg_parser import SVGParser

        dot_spacing = self.config.get("normal_welds", "dot_spacing")
        parser = SVGParser(dot_spacing=dot_spacing)

        publish_event(ParsingEvent("parsing_svg", svg_path))
        weld_paths = parser.parse_file(str(svg_path))

        return weld_paths

    def _parse_dxf_file(self, dxf_path: Path) -> List[WeldPath]:
        """Parse DXF file."""
        from .dxf_reader import DXFReader

        publish_event(ParsingEvent("parsing_dxf", dxf_path))

        # Create DXF reader
        reader = DXFReader()

        weld_paths = reader.parse_file(dxf_path)
        return weld_paths

    def _process_weld_paths_via_events(self, weld_paths: List[WeldPath]) -> None:
        """Process weld paths by publishing events."""
        publish_event(
            PathEvent("start_processing", "all_paths", total_paths=len(weld_paths))
        )

        for i, path in enumerate(weld_paths):
            # Publish path start event
            publish_event(
                PathEvent(
                    "path_start",
                    path.svg_id,
                    path_data={
                        "id": path.svg_id,
                        "weld_type": path.weld_type,
                        "point_count": len(path.points),
                    },
                )
            )

            # Publish point events
            for j, point in enumerate(path.points):
                publish_event(
                    PointEvent(
                        "point_added",
                        {"x": point.x, "y": point.y, "weld_type": point.weld_type},
                    )
                )

                # Publish progress
                if j % 10 == 0:  # Every 10th point
                    publish_event(
                        ProgressEvent(
                            stage=f"path_{path.svg_id}",
                            progress=j,
                            total=len(path.points),
                        )
                    )

            # Publish path complete event
            publish_event(
                PathEvent(
                    "path_complete",
                    path.svg_id,
                    path_data={
                        "id": path.svg_id,
                        "weld_type": path.weld_type,
                        "points": [
                            {"x": p.x, "y": p.y, "weld_type": p.weld_type}
                            for p in path.points
                        ],
                    },
                )
            )

            # Publish overall progress
            publish_event(
                ProgressEvent(
                    stage="processing_paths", progress=i + 1, total=len(weld_paths)
                )
            )

    def get_statistics(self) -> Dict:
        """Get processing statistics."""
        stats_subscriber = self.subscriber_factory.get_statistics_subscriber()
        return stats_subscriber.get_statistics() if stats_subscriber else {}

    def get_validation_results(self) -> Dict:
        """Get validation results."""
        if self.use_two_phase:
            return self.two_phase_processor.get_validation_results()

        validation_subscriber = self.subscriber_factory.get_validation_subscriber()
        return (
            validation_subscriber.get_validation_results()
            if validation_subscriber
            else {}
        )

    def clear_validation_results(self) -> None:
        """Clear validation results."""
        if self.use_two_phase:
            self.two_phase_processor.clear_validation_results()
            return

        validation_subscriber = self.subscriber_factory.get_validation_subscriber()
        if validation_subscriber:
            validation_subscriber.reset()

    def reset_statistics(self) -> None:
        """Reset processing statistics."""
        stats_subscriber = self.subscriber_factory.get_statistics_subscriber()
        if stats_subscriber:
            stats_subscriber.reset_statistics()


def create_processor(config: Config, verbose: bool = False) -> EventDrivenProcessor:
    """Create an event-driven processor instance."""
    return EventDrivenProcessor(config, verbose=verbose)
