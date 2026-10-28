"""Geometry helpers for projecting normalized seats onto a theatre plan."""

from math import atan2, ceil, cos, degrees, radians, sin, sqrt


def row_slot_positions(
    row, *, max_position: int, geometry: dict | None = None
) -> dict[float, tuple[float, float, float]]:
    """Return deterministic x, y and rotation values for seat and gap slots."""
    geometry = geometry or row_layout_data(row)
    shape = geometry["shape"]

    positions = {seat.position: seat.position for seat in row.seats.all()}
    for gap in row.gaps.all():
        center_position = gap.position + (gap.width - 1) / 2
        positions[center_position] = center_position

    projected = {}
    for slot_position in positions:
        fraction = (
            0.5
            if max_position <= 1
            else max(0.0, min(1.0, (slot_position - 1) / (max_position - 1)))
        )
        if shape == "straight":
            start_x, start_y = geometry["startX"], geometry["startY"]
            end_x, end_y = geometry["endX"], geometry["endY"]
            x = start_x + (end_x - start_x) * fraction
            y = start_y + (end_y - start_y) * fraction
            rotation = degrees(atan2(end_y - start_y, end_x - start_x))
        else:
            angle = (
                geometry["startAngle"]
                + (geometry["endAngle"] - geometry["startAngle"]) * fraction
            )
            angle_radians = radians(angle)
            x = geometry["centerX"] + geometry["radiusX"] * cos(angle_radians)
            y = geometry["centerY"] + geometry["radiusY"] * sin(angle_radians)
            rotation = angle + 90
        projected[slot_position] = (
            round(x, 2),
            round(y, 2),
            round(((rotation + 180) % 360) - 180, 2),
        )
    return projected


def row_layout_data(
    row,
    *,
    section_layout: dict | None = None,
    row_index: int = 0,
    row_count: int = 1,
) -> dict:
    """Serialize row geometry without exposing model internals."""
    layout = getattr(row, "layout", None)
    if layout is None:
        section_layout = section_layout or {
            "x": 80,
            "y": 130,
            "width": 1040,
            "height": 580,
        }
        row_y = round(
            section_layout["y"]
            + section_layout["height"] * (row_index + 1) / (row_count + 1)
        )
        return {
            "shape": "straight",
            "startX": section_layout["x"] + 24,
            "startY": row_y,
            "endX": section_layout["x"] + section_layout["width"] - 24,
            "endY": row_y,
        }
    if layout.shape == "straight":
        return {
            "shape": layout.shape,
            "startX": layout.start_x,
            "startY": layout.start_y,
            "endX": layout.end_x,
            "endY": layout.end_y,
        }
    return {
        "shape": layout.shape,
        "centerX": layout.center_x,
        "centerY": layout.center_y,
        "radiusX": layout.radius_x,
        "radiusY": layout.radius_y,
        "startAngle": float(layout.start_angle),
        "endAngle": float(layout.end_angle),
    }


def section_layout_data(
    section,
    *,
    section_index: int = 0,
    section_count: int = 1,
    row_count: int = 1,
) -> dict:
    """Serialize section geometry with a linear rectangle fallback."""
    layout = getattr(section, "layout", None)
    if layout is None:
        columns = ceil(sqrt(max(1, section_count)))
        grid_row_count = ceil(max(1, section_count) / columns)
        cell_width = 1060 / columns
        cell_height = 600 / grid_row_count
        column_index = section_index % columns
        row_index = section_index // columns
        return {
            "shape": "rectangle",
            "levelName": "Planta principal",
            "levelOrder": 0,
            "x": round(70 + column_index * cell_width + 8),
            "y": round(130 + row_index * cell_height + 8),
            "width": max(1, round(cell_width - 16)),
            "height": max(
                1,
                round(min(cell_height - 16, max(120, row_count * 54 + 64))),
            ),
            "rotation": 0,
            "innerRadiusRatio": 0.55,
            "startAngle": 205,
            "endAngle": 335,
        }
    return {
        "shape": layout.shape,
        "levelName": layout.level_name,
        "levelOrder": layout.level_order,
        "x": layout.x,
        "y": layout.y,
        "width": layout.width,
        "height": layout.height,
        "rotation": layout.rotation,
        "innerRadiusRatio": float(layout.inner_radius_ratio),
        "startAngle": float(layout.start_angle),
        "endAngle": float(layout.end_angle),
    }


def map_layout_data(map_version) -> dict:
    """Serialize the canvas and stage, falling back for pre-layout records."""
    layout = getattr(map_version, "layout", None)
    if layout is None:
        return {
            "width": 1200,
            "height": 800,
            "stage": {
                "x": 400,
                "y": 30,
                "width": 400,
                "height": 70,
                "label": "ESCENARIO",
            },
        }
    return {
        "width": layout.width,
        "height": layout.height,
        "stage": {
            "x": layout.stage_x,
            "y": layout.stage_y,
            "width": layout.stage_width,
            "height": layout.stage_height,
            "label": layout.stage_label,
        },
    }
