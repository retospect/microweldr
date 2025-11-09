"""DXF file reader with publisher-subscriber architecture."""

import logging
import math
from pathlib import Path
from typing import List, Optional, Dict, Any

from .app_constants import DXFEntities, LayerTypes
from .data_models import (
    Point,
    WeldPath,
    WeldType,
    LineEntity,
    ArcEntity,
    CircleEntity,
    CADEntity,
)
from .error_handling import FileProcessingError, ParsingError, handle_errors
from .file_readers import FileReaderPublisher

logger = logging.getLogger(__name__)

try:
    import ezdxf

    DXF_AVAILABLE = True
except ImportError:
    DXF_AVAILABLE = False
    logger.warning("ezdxf not available - DXF reading disabled")


class DXFReader(FileReaderPublisher):
    """DXF file reader that publishes weld paths."""

    def __init__(self):
        super().__init__()
        if not DXF_AVAILABLE:
            raise ImportError(
                "ezdxf library is required for DXF reading. Install with: pip install ezdxf"
            )

    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return [".dxf", ".DXF"]

    def can_read_file(self, file_path: Path) -> bool:
        """Check if this reader can handle the given file."""
        return file_path.suffix.lower() in self.get_supported_extensions()

    @handle_errors(
        error_types={
            **(
                {
                    ezdxf.DXFError: ParsingError,
                    ezdxf.DXFStructureError: ParsingError,
                }
                if DXF_AVAILABLE
                else {}
            ),
            ValueError: ParsingError,
        },
        default_error=FileProcessingError,
    )
    def _parse_file_internal(self, file_path: Path) -> List[WeldPath]:
        """Parse DXF file and extract weld paths."""
        logger.info(f"Parsing DXF file: {file_path}")

        # Store filename for weld type detection
        self._current_filename = file_path.stem

        try:
            # Load DXF document
            doc = ezdxf.readfile(str(file_path))

            # Validate units
            self._validate_units(doc)

            # Get model space
            msp = doc.modelspace()

            # Parse entities
            entities = self._parse_entities(msp)

            # Convert to weld paths
            weld_paths = self._entities_to_weld_paths(entities)

            logger.info(
                f"Parsed {len(weld_paths)} weld paths from {len(entities)} entities"
            )
            return weld_paths

        except ezdxf.DXFError as e:
            raise ParsingError(f"DXF parsing error: {e}")
        except Exception as e:
            raise FileProcessingError(f"Failed to parse DXF file {file_path}: {e}")

    def _validate_units(self, doc: "ezdxf.document.Drawing") -> None:
        """Validate that DXF units are in millimeters."""
        header = doc.header

        # Check INSUNITS (insertion units)
        insunits = header.get("$INSUNITS", 0)

        # INSUNITS values: 0=Unitless, 1=Inches, 2=Feet, 4=Millimeters, 5=Centimeters, 6=Meters
        if insunits == 4:
            logger.debug("DXF units confirmed as millimeters")
            return
        elif insunits == 0:
            logger.warning("DXF units are unitless - assuming millimeters")
            return
        else:
            unit_names = {1: "inches", 2: "feet", 5: "centimeters", 6: "meters"}
            unit_name = unit_names.get(insunits, f"unknown ({insunits})")
            raise ParsingError(
                f"DXF file must use millimeter units, but found {unit_name}. "
                f"Please convert your DXF file to use millimeter units."
            )

    def _parse_entities(self, msp) -> List[CADEntity]:
        """Parse entities from model space."""
        entities = []

        for entity in msp:
            try:
                parsed_entity = self._parse_entity(entity)
                if parsed_entity:
                    entities.append(parsed_entity)
            except Exception as e:
                logger.warning(f"Failed to parse entity {entity.dxftype()}: {e}")
                continue

        return entities

    def _parse_entity(self, entity) -> Optional[CADEntity]:
        """Parse a single DXF entity."""
        entity_type = entity.dxftype()
        layer = entity.dxf.layer or "0"

        if entity_type == DXFEntities.LINE:
            return self._parse_line(entity, layer)
        elif entity_type == DXFEntities.ARC:
            return self._parse_arc(entity, layer)
        elif entity_type == DXFEntities.CIRCLE:
            return self._parse_circle(entity, layer)
        elif entity_type in [DXFEntities.POLYLINE, DXFEntities.LWPOLYLINE]:
            return self._parse_polyline(entity, layer)
        else:
            logger.debug(f"Unsupported entity type: {entity_type}")
            return None

    def _parse_line(self, entity, layer: str) -> LineEntity:
        """Parse a LINE entity."""
        start_point = entity.dxf.start
        end_point = entity.dxf.end

        return LineEntity(
            layer=layer,
            entity_type=DXFEntities.LINE,
            start=Point(start_point.x, start_point.y),
            end=Point(end_point.x, end_point.y),
        )

    def _parse_arc(self, entity, layer: str) -> ArcEntity:
        """Parse an ARC entity."""
        center = entity.dxf.center
        radius = entity.dxf.radius
        start_angle = entity.dxf.start_angle
        end_angle = entity.dxf.end_angle

        return ArcEntity(
            layer=layer,
            entity_type=DXFEntities.ARC,
            center=Point(center.x, center.y),
            radius=radius,
            start_angle=start_angle,
            end_angle=end_angle,
        )

    def _parse_circle(self, entity, layer: str) -> CircleEntity:
        """Parse a CIRCLE entity."""
        center = entity.dxf.center
        radius = entity.dxf.radius

        return CircleEntity(
            layer=layer,
            entity_type=DXFEntities.CIRCLE,
            center=Point(center.x, center.y),
            radius=radius,
        )

    def _parse_polyline(self, entity, layer: str) -> Optional[LineEntity]:
        """Parse POLYLINE/LWPOLYLINE entities as connected line segments."""
        # For now, convert polylines to individual line segments
        # This could be enhanced to create proper polyline entities
        points = []

        if hasattr(entity, "vertices"):
            # POLYLINE
            for vertex in entity.vertices:
                if hasattr(vertex.dxf, "location"):
                    loc = vertex.dxf.location
                    points.append(Point(loc.x, loc.y))
        else:
            # LWPOLYLINE
            for point in entity:
                points.append(Point(point[0], point[1]))

        if len(points) >= 2:
            # For now, just return the first line segment
            # TODO: Handle polylines as multiple connected segments
            return LineEntity(
                layer=layer,
                entity_type="POLYLINE_SEGMENT",
                start=points[0],
                end=points[1],
            )

        return None

    def _entities_to_weld_paths(self, entities: List[CADEntity]) -> List[WeldPath]:
        """Convert CAD entities to weld paths."""
        weld_paths = []

        for entity in entities:
            # Skip construction entities
            if entity.is_construction:
                logger.debug(f"Skipping construction entity on layer: {entity.layer}")
                continue

            # Determine weld type based on layer name
            weld_type = self._determine_weld_type(entity.layer)

            try:
                if isinstance(entity, LineEntity):
                    path = entity.to_weld_path(weld_type)
                elif isinstance(entity, ArcEntity):
                    path = entity.to_weld_path(segments=20, weld_type=weld_type)
                elif isinstance(entity, CircleEntity):
                    path = entity.to_weld_path(segments=36, weld_type=weld_type)
                else:
                    logger.warning(f"Unknown entity type: {type(entity)}")
                    continue

                weld_paths.append(path)
                logger.debug(
                    f"Converted {entity.entity_type} on layer '{entity.layer}' to {weld_type.value} weld path"
                )

            except Exception as e:
                logger.error(
                    f"Failed to convert entity {entity.entity_type} to weld path: {e}"
                )
                continue

        return weld_paths

    def _determine_weld_type(self, layer_name: str) -> WeldType:
        """Determine weld type based on layer name and filename."""
        layer_lower = layer_name.lower()

        # First check layer name for frangible indicators
        frangible_keywords = ["frangible", "light", "break", "seal", "weak"]
        if any(keyword in layer_lower for keyword in frangible_keywords):
            return WeldType.FRANGIBLE

        # Fallback: Check filename for frangible indicators
        if hasattr(self, "_current_filename") and self._current_filename:
            filename_lower = self._current_filename.lower()
            if any(keyword in filename_lower for keyword in frangible_keywords):
                return WeldType.FRANGIBLE

        # Default to normal welds
        return WeldType.NORMAL

    def get_layer_info(self, file_path: Path) -> Dict[str, Any]:
        """Get information about layers in the DXF file."""
        if not DXF_AVAILABLE:
            return {}

        try:
            doc = ezdxf.readfile(str(file_path))
            layer_info = {}

            for layer in doc.layers:
                layer_name = layer.dxf.name
                layer_info[layer_name] = {
                    "color": layer.dxf.color,
                    "linetype": layer.dxf.linetype,
                    "is_construction": any(
                        pattern in layer_name.lower()
                        for pattern in [
                            "construction",
                            "const",
                            "guide",
                            "reference",
                            "ref",
                        ]
                    ),
                }

            return layer_info

        except Exception as e:
            logger.error(f"Failed to get layer info from {file_path}: {e}")
            return {}


# Factory function for easy instantiation
def create_dxf_reader() -> Optional[DXFReader]:
    """Create a DXF reader if ezdxf is available."""
    try:
        return DXFReader()
    except ImportError as e:
        logger.warning(f"Cannot create DXF reader: {e}")
        return None
