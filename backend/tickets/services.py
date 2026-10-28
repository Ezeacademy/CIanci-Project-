from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from .models import (
    FunctionSectionPrice,
    Seat,
    SeatGap,
    SeatMapVersion,
    SeatRow,
    SeatSection,
    ShowFunction,
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
    copied_sections = []
    for section in source.sections.prefetch_related("rows__seats", "rows__gaps"):
        section_data = {
            "name": section.name,
            "sortOrder": section.sort_order,
            "rows": [],
        }
        for row in section.rows.all():
            section_data["rows"].append(
                {
                    "label": row.label,
                    "sortOrder": row.sort_order,
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
def replace_map_structure(version_id: int, sections: list[dict]) -> SeatMapVersion:
    """Replace a draft map structure atomically; function-linked maps are immutable."""
    version = SeatMapVersion.objects.select_for_update().get(pk=version_id)
    if version.is_frozen:
        raise ValidationError(
            "Esta versión está asociada a una función. "
            "Creá una nueva versión para editar el mapa."
        )
    section_ids = list(version.sections.values_list("pk", flat=True))
    row_ids = list(
        SeatRow.objects.filter(section_id__in=section_ids).values_list("pk", flat=True)
    )
    Seat.objects.filter(row_id__in=row_ids).delete()
    SeatGap.objects.filter(row_id__in=row_ids).delete()
    SeatRow.objects.filter(pk__in=row_ids).delete()
    SeatSection.objects.filter(pk__in=section_ids).delete()
    _write_sections(version, sections)
    return version


def _write_sections(version: SeatMapVersion, sections: list[dict]) -> None:
    for section_index, section_data in enumerate(sections):
        section = SeatSection.objects.create(
            map_version=version,
            name=section_data["name"].strip(),
            sort_order=section_data.get("sortOrder", section_index),
        )
        for row_index, row_data in enumerate(section_data.get("rows", [])):
            row = SeatRow.objects.create(
                section=section,
                label=row_data["label"].strip(),
                sort_order=row_data.get("sortOrder", row_index),
            )
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
