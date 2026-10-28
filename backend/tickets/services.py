from math import ceil, sqrt

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from .models import (
    FunctionSectionPrice,
    Seat,
    SeatGap,
    SeatMapLayout,
    SeatMapVersion,
    SeatRow,
    SeatRowLayout,
    SeatSection,
    SeatSectionLayout,
    Show,
    ShowFunction,
    TicketingDeletionAudit,
    Venue,
)


@transaction.atomic
def create_map_version(venue_id: int, actor, sections: list[dict]) -> SeatMapVersion:
    """Create an editable, normalized seat-map version for a venue.

    Locking the venue serializes version-number allocation across concurrent
    administrators. Every structural child is created in the same transaction.
    """
    venue = Venue.objects.select_for_update().get(pk=venue_id)
    next_number = (
        venue.map_versions.aggregate(number=Max("version_number"))["number"] or 0
    ) + 1
    version = SeatMapVersion.objects.create(
        venue=venue, version_number=next_number, created_by=actor
    )
    SeatMapLayout.objects.create(map_version=version)
    _write_sections(version, sections)
    return version


@transaction.atomic
def create_map_version_from(existing_version_id: int, actor) -> SeatMapVersion:
    """Copy a map into a new editable version, preserving its physical layout."""
    source = SeatMapVersion.objects.select_for_update().get(pk=existing_version_id)
    venue = Venue.objects.select_for_update().get(pk=source.venue_id)
    next_number = (
        venue.map_versions.aggregate(number=Max("version_number"))["number"] or 0
    ) + 1
    version = SeatMapVersion.objects.create(
        venue=venue, version_number=next_number, created_by=actor
    )
    source_layout = getattr(source, "layout", None)
    if source_layout:
        SeatMapLayout.objects.create(
            map_version=version,
            width=source_layout.width,
            height=source_layout.height,
            stage_x=source_layout.stage_x,
            stage_y=source_layout.stage_y,
            stage_width=source_layout.stage_width,
            stage_height=source_layout.stage_height,
            stage_label=source_layout.stage_label,
        )
    else:
        SeatMapLayout.objects.create(map_version=version)
    copied_sections = []
    for section in source.sections.prefetch_related(
        "layout", "rows__layout", "rows__seats", "rows__gaps"
    ):
        section_data = {
            "name": section.name,
            "sortOrder": section.sort_order,
            "layout": _section_layout_values(section),
            "rows": [],
        }
        for row in section.rows.all():
            section_data["rows"].append(
                {
                    "label": row.label,
                    "sortOrder": row.sort_order,
                    "layout": _row_layout_values(row),
                    "seats": [
                        {
                            "number": seat.number,
                            "position": seat.position,
                            "isAccessible": seat.is_accessible,
                            "isOperational": seat.is_operational,
                        }
                        for seat in row.seats.all()
                    ],
                    "gaps": [
                        {"position": gap.position, "width": gap.width, "kind": gap.kind}
                        for gap in row.gaps.all()
                    ],
                }
            )
        copied_sections.append(section_data)
    _write_sections(version, copied_sections)
    return version


@transaction.atomic
def replace_map_structure(
    version_id: int, sections: list[dict], actor=None
) -> SeatMapVersion:
    """Replace a draft map structure atomically; function-linked maps are immutable."""
    version = SeatMapVersion.objects.select_for_update().get(pk=version_id)
    if version.is_frozen:
        raise ValidationError(
            "Esta versión está asociada a una función. "
            "Creá una nueva versión para editar el mapa."
        )
    preserved_layouts = {}
    for existing_section in version.sections.prefetch_related("layout", "rows__layout"):
        section_layout = getattr(existing_section, "layout", None)
        row_layouts = {
            existing_row.label: _row_layout_values(existing_row)
            for existing_row in existing_section.rows.all()
        }
        preserved_layouts[existing_section.name] = (
            _section_layout_values(existing_section) if section_layout else None,
            row_layouts,
        )
    sections = _preserve_existing_layouts(sections, preserved_layouts)
    section_ids = list(version.sections.values_list("pk", flat=True))
    row_ids = list(
        SeatRow.objects.filter(section_id__in=section_ids).values_list("pk", flat=True)
    )
    Seat.objects.filter(row_id__in=row_ids).delete()
    SeatGap.objects.filter(row_id__in=row_ids).delete()
    SeatRow.objects.filter(pk__in=row_ids).delete()
    SeatSection.objects.filter(pk__in=section_ids).delete()
    _write_sections(version, sections)
    version.updated_by = actor
    version.save(update_fields=("updated_by", "updated_at"))
    return version


def _write_sections(version: SeatMapVersion, sections: list[dict]) -> None:
    map_layout, _ = SeatMapLayout.objects.get_or_create(map_version=version)
    section_count = max(1, len(sections))
    columns = ceil(sqrt(section_count))
    rows = ceil(section_count / columns)
    usable_x = 70
    usable_y = map_layout.stage_y + map_layout.stage_height + 36
    usable_width = max(100, map_layout.width - 2 * usable_x)
    usable_height = max(100, map_layout.height - usable_y - 40)
    cell_width = usable_width / columns
    cell_height = usable_height / rows
    for section_index, section_data in enumerate(sections):
        column_index = section_index % columns
        row_index = section_index // columns
        default_section_layout = {
            "shape": SeatSectionLayout.Shape.RECTANGLE,
            "level_name": "Planta principal",
            "level_order": 0,
            "x": round(usable_x + column_index * cell_width + 8),
            "y": round(usable_y + row_index * cell_height + 8),
            "width": max(1, round(cell_width - 16)),
            "height": max(1, round(cell_height - 16)),
        }
        section_layout_values = {
            **default_section_layout,
            **section_data.get("layout", {}),
        }
        section = SeatSection.objects.create(
            map_version=version,
            name=section_data["name"].strip(),
            sort_order=section_data.get("sortOrder", section_index),
        )
        SeatSectionLayout.objects.create(section=section, **section_layout_values)
        section_rows = section_data.get("rows", [])
        section_top = section_layout_values["y"]
        section_height = section_layout_values["height"]
        for row_index, row_data in enumerate(section_data.get("rows", [])):
            row = SeatRow.objects.create(
                section=section,
                label=row_data["label"].strip(),
                sort_order=row_data.get("sortOrder", row_index),
            )
            row_y = round(
                section_top + section_height * (row_index + 1) / (len(section_rows) + 1)
            )
            default_row_layout = {
                "shape": SeatRowLayout.Shape.STRAIGHT,
                "start_x": section_layout_values["x"] + 24,
                "start_y": row_y,
                "end_x": section_layout_values["x"]
                + section_layout_values["width"]
                - 24,
                "end_y": row_y,
            }
            row_layout_values = {**default_row_layout, **row_data.get("layout", {})}
            SeatRowLayout.objects.create(row=row, **row_layout_values)
            for seat_data in row_data.get("seats", []):
                Seat.objects.create(
                    row=row,
                    number=str(seat_data["number"]).strip(),
                    position=seat_data["position"],
                    is_accessible=seat_data.get("isAccessible", False),
                    is_operational=seat_data.get("isOperational", True),
                )
            for gap_data in row_data.get("gaps", []):
                SeatGap.objects.create(
                    row=row,
                    position=gap_data["position"],
                    width=gap_data.get("width", 1),
                    kind=gap_data.get("kind", SeatGap.Kind.AISLE),
                )


def _section_layout_values(section) -> dict:
    """Copy only the persisted visual fields for a section."""
    layout = getattr(section, "layout", None)
    if layout is None:
        return {}
    return {
        field: getattr(layout, field)
        for field in (
            "shape",
            "level_name",
            "level_order",
            "x",
            "y",
            "width",
            "height",
            "rotation",
            "inner_radius_ratio",
            "start_angle",
            "end_angle",
        )
    }


def _row_layout_values(row) -> dict:
    """Copy only the persisted visual fields for a row."""
    layout = getattr(row, "layout", None)
    if layout is None:
        return {}
    return {
        field: getattr(layout, field)
        for field in (
            "shape",
            "start_x",
            "start_y",
            "end_x",
            "end_y",
            "center_x",
            "center_y",
            "radius_x",
            "radius_y",
            "start_angle",
            "end_angle",
        )
    }


def _preserve_existing_layouts(
    sections: list[dict], existing_layouts: dict
) -> list[dict]:
    """Carry matching section and row geometry through structural replacement."""
    preserved_sections = []
    for section_data in sections:
        section_copy = {**section_data}
        existing_section_layout, existing_row_layouts = existing_layouts.get(
            section_copy["name"], (None, {})
        )
        if "layout" not in section_copy and existing_section_layout:
            section_copy["layout"] = existing_section_layout
        preserved_rows = []
        for row_data in section_copy.get("rows", []):
            row_copy = {**row_data}
            if "layout" not in row_copy and row_copy["label"] in existing_row_layouts:
                row_copy["layout"] = existing_row_layouts[row_copy["label"]]
            preserved_rows.append(row_copy)
        section_copy["rows"] = preserved_rows
        preserved_sections.append(section_copy)
    return preserved_sections


@transaction.atomic
def create_show_function(*, show, map_version, starts_at, section_prices, actor=None):
    """Attach a function to one specific map version and its independent prices."""
    version = SeatMapVersion.objects.select_for_update().get(pk=map_version.pk)
    function = ShowFunction.objects.create(
        show=show, map_version=version, starts_at=starts_at, created_by=actor
    )
    for price in section_prices:
        FunctionSectionPrice.objects.create(
            function=function,
            section_id=price["section_id"],
            amount=price["amount"],
        )
    return function


@transaction.atomic
def update_show_function(
    *, function_id: int, actor, starts_at=None, section_prices=None
) -> ShowFunction:
    """Update a function's time and prices as one audited operation.

    The function row serializes concurrent edits. Prices are locked in primary-key
    order and only submitted sectors change, so omitted prices remain untouched.
    """
    function = ShowFunction.objects.select_for_update().get(pk=function_id)
    existing_prices = list(
        FunctionSectionPrice.objects.select_for_update()
        .filter(function=function)
        .order_by("pk")
    )
    prices_by_section = {price.section_id: price for price in existing_prices}

    if starts_at is not None:
        function.starts_at = starts_at

    if section_prices is not None:
        section_ids = [price["section_id"] for price in section_prices]
        if len(section_ids) != len(set(section_ids)):
            raise ValidationError("No repitas sectores en los precios de la función.")

        map_section_ids = set(
            SeatSection.objects.filter(
                map_version_id=function.map_version_id
            ).values_list("pk", flat=True)
        )
        if not set(section_ids).issubset(map_section_ids):
            raise ValidationError(
                "Los precios deben pertenecer al mapa de esta función."
            )

        for price_data in section_prices:
            section_id = price_data["section_id"]
            price = prices_by_section.get(section_id)
            if price is None:
                price = FunctionSectionPrice(
                    function=function,
                    section_id=section_id,
                    amount=price_data["amount"],
                )
            else:
                price.amount = price_data["amount"]
            price.save()

    function.updated_by = actor
    function.save(update_fields=("starts_at", "updated_by", "updated_at"))
    return function


@transaction.atomic
def delete_show(show_id: int, actor) -> None:
    """Delete a show only when it has no functions or protected history."""
    show = Show.objects.select_for_update().get(pk=show_id)
    if show.functions.exists():
        raise ValidationError(
            "No se puede eliminar este espectáculo porque tiene funciones. "
            "Archivarlo conserva su historial."
        )
    TicketingDeletionAudit.objects.create(
        entity_type=TicketingDeletionAudit.EntityType.SHOW,
        object_id=show.pk,
        object_label=show.title,
        deleted_by=actor,
    )
    show.delete()


@transaction.atomic
def delete_show_function(function_id: int, actor) -> None:
    """Delete a function and its prices unless protected records reference it."""
    function = (
        ShowFunction.objects.select_for_update()
        .select_related("show")
        .get(pk=function_id)
    )
    TicketingDeletionAudit.objects.create(
        entity_type=TicketingDeletionAudit.EntityType.FUNCTION,
        object_id=function.pk,
        object_label=str(function),
        deleted_by=actor,
    )
    FunctionSectionPrice.objects.filter(function=function).delete()
    function.delete()


@transaction.atomic
def delete_venue(venue_id: int, actor) -> None:
    """Delete an unused venue; maps must be explicitly removed first."""
    venue = Venue.objects.select_for_update().get(pk=venue_id)
    if venue.map_versions.exists():
        raise ValidationError(
            "No se puede eliminar este recinto porque todavía tiene versiones "
            "de mapas. Eliminá primero los mapas que no estén asociados a funciones."
        )
    TicketingDeletionAudit.objects.create(
        entity_type=TicketingDeletionAudit.EntityType.VENUE,
        object_id=venue.pk,
        object_label=venue.name,
        deleted_by=actor,
    )
    venue.delete()


@transaction.atomic
def delete_seat_map_version(version_id: int, actor) -> None:
    """Delete an unassigned map after explicitly removing its physical layout."""
    version = (
        SeatMapVersion.objects.select_for_update()
        .select_related("venue")
        .get(pk=version_id)
    )
    if version.functions.exists():
        raise ValidationError(
            "No se puede eliminar esta versión porque está asociada a una función."
        )
    TicketingDeletionAudit.objects.create(
        entity_type=TicketingDeletionAudit.EntityType.SEAT_MAP,
        object_id=version.pk,
        object_label=str(version),
        deleted_by=actor,
    )
    section_ids = list(version.sections.values_list("pk", flat=True))
    row_ids = list(
        SeatRow.objects.filter(section_id__in=section_ids).values_list("pk", flat=True)
    )
    Seat.objects.filter(row_id__in=row_ids).delete()
    SeatGap.objects.filter(row_id__in=row_ids).delete()
    SeatRow.objects.filter(pk__in=row_ids).delete()
    SeatSection.objects.filter(pk__in=section_ids).delete()
    version.delete()
