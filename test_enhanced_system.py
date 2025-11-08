#!/usr/bin/env python3
"""Test script for the enhanced event-driven system with curve support."""

from pathlib import Path
from microweldr.core.config import Config
from microweldr.core.enhanced_converter import EnhancedSVGToGCodeConverter
from microweldr.core.enhanced_converter import (
    JSONExportSubscriber,
    RealTimeMonitorSubscriber,
)


def test_flask_component():
    """Test the enhanced system with the flask component that has curves."""

    # Set up paths
    svg_path = Path("examples/flask_component.svg")
    gcode_path = Path("test_output_enhanced.gcode")
    animation_path = Path("test_output_enhanced.svg")
    json_path = Path("test_output_enhanced.json")

    print("🧪 Testing Enhanced Event-Driven System with Curve Support")
    print("=" * 60)

    # Load config
    config = Config()

    # Create enhanced converter
    converter = EnhancedSVGToGCodeConverter(config, verbose=True)

    # Add custom subscribers
    json_subscriber = JSONExportSubscriber(json_path)
    converter.add_subscriber(json_subscriber)

    # Real-time monitoring callback
    def monitor_callback(event, status):
        if hasattr(event, "curve_type"):
            print(f"🌊 Real-time: {event.curve_type} curve processed")

    monitor_subscriber = RealTimeMonitorSubscriber(monitor_callback)
    converter.add_subscriber(monitor_subscriber)

    try:
        print(f"📁 Input SVG: {svg_path}")
        print(f"📁 Output G-code: {gcode_path}")
        print(f"📁 Output Animation: {animation_path}")
        print(f"📁 Output JSON: {json_path}")
        print()

        # Convert with all outputs
        weld_paths = converter.convert_with_events(
            svg_path=svg_path,
            gcode_path=gcode_path,
            animation_path=animation_path,
            enable_statistics=True,
        )

        print()
        print("🎉 Conversion Results:")
        print(f"   Total paths: {len(weld_paths)}")
        print(f"   Total points: {sum(len(path.points) for path in weld_paths)}")
        print(f"   Supported curves: {converter.get_supported_curve_types()}")

        # Check for curve-related events
        curve_events = [
            e
            for e in converter.get_event_history()
            if hasattr(e, "event_type") and "CURVE" in str(e.event_type)
        ]

        print(f"   Curves processed: {len(curve_events)}")

        for event in curve_events:
            if hasattr(event, "curve_type") and hasattr(event, "approximated_points"):
                curve_type = event.curve_type
                points_count = (
                    len(event.approximated_points) if event.approximated_points else 0
                )
                print(f"     - {curve_type}: {points_count} points")

        # Verify outputs exist
        outputs_created = []
        if gcode_path.exists():
            outputs_created.append(f"G-code ({gcode_path.stat().st_size} bytes)")
        if animation_path.exists():
            outputs_created.append(f"Animation ({animation_path.stat().st_size} bytes)")
        if json_path.exists():
            outputs_created.append(f"JSON ({json_path.stat().st_size} bytes)")

        print(f"   Files created: {', '.join(outputs_created)}")

        return True

    except Exception as e:
        print(f"❌ Error during conversion: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_streaming_mode():
    """Test streaming mode with custom subscribers."""

    print("\n🚀 Testing Streaming Mode")
    print("=" * 30)

    svg_path = Path("examples/flask_component.svg")
    config = Config()
    converter = EnhancedSVGToGCodeConverter(config, verbose=True)

    # Custom streaming subscriber
    class StreamingSubscriber:
        def __init__(self):
            self.point_count = 0

        def get_subscribed_events(self):
            from microweldr.core.events import EventType

            return {EventType.POINTS_BATCH, EventType.CURVE_APPROXIMATED}

        def handle_event(self, event):
            from microweldr.core.events import EventType

            if event.event_type == EventType.POINTS_BATCH:
                if hasattr(event, "points") and event.points:
                    self.point_count += len(event.points)
                    print(f"📊 Streaming: {self.point_count} total points processed")
            elif event.event_type == EventType.CURVE_APPROXIMATED:
                if hasattr(event, "curve_type"):
                    print(f"🌊 Streaming: {event.curve_type} curve approximated")

    streaming_sub = StreamingSubscriber()

    try:
        weld_paths = converter.convert_streaming(svg_path, [streaming_sub])
        print(f"✅ Streaming conversion completed: {len(weld_paths)} paths")
        return True
    except Exception as e:
        print(f"❌ Streaming error: {e}")
        return False


if __name__ == "__main__":
    success1 = test_flask_component()
    success2 = test_streaming_mode()

    if success1 and success2:
        print("\n🎉 All tests passed! Enhanced system working correctly.")
    else:
        print("\n❌ Some tests failed. Check the output above.")
