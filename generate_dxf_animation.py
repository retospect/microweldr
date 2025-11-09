#!/usr/bin/env python3
"""Generate animation from DXF file using MicroWeldr components."""

import sys
from pathlib import Path
from microweldr.core.dxf_reader import DXFReader
from microweldr.animation.generator import AnimationGenerator
from microweldr.core.config import Config


def generate_dxf_animation(dxf_file: str, output_base: str = None):
    """Generate animation from DXF file."""
    dxf_path = Path(dxf_file)

    if not dxf_path.exists():
        print(f"❌ DXF file not found: {dxf_file}")
        return False

    if output_base is None:
        output_base = dxf_path.stem

    print(f"🔥 MicroWeldr - DXF Animation Generation")
    print("=" * 50)
    print(f"📁 Input: {dxf_file}")

    try:
        # Load configuration
        config = Config("config.toml")
        print("✓ Configuration loaded")

        # Parse DXF file
        print("🔧 Parsing DXF file...")
        reader = DXFReader()
        weld_paths = reader.parse_file(dxf_path)

        if not weld_paths:
            print("❌ No weld paths found in DXF file")
            return False

        print(f"✓ Found {len(weld_paths)} weld paths")

        # Show weld path details
        normal_count = sum(1 for p in weld_paths if p.weld_type.value == "normal")
        frangible_count = sum(1 for p in weld_paths if p.weld_type.value == "frangible")

        print(f"  - Normal welds: {normal_count}")
        print(f"  - Frangible welds: {frangible_count}")

        # Generate animation
        print("🎬 Generating animation...")
        animation_file = f"{output_base}_animation.svg"

        generator = AnimationGenerator(config)
        generator.generate_animation(weld_paths, animation_file)

        print(f"✅ Animation saved: {animation_file}")
        print(f"🌐 Open {animation_file} in a web browser to view the animation")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_dxf_animation.py <dxf_file> [output_base]")
        print("Example: python generate_dxf_animation.py flask-weld.dxf")
        sys.exit(1)

    dxf_file = sys.argv[1]
    output_base = sys.argv[2] if len(sys.argv) > 2 else None

    success = generate_dxf_animation(dxf_file, output_base)
    sys.exit(0 if success else 1)
