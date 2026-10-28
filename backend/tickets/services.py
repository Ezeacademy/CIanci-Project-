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
    function = ShowFunction.objects.select_for_update().select_related("show").get(
        pk=function_id
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
    version = SeatMapVersion.objects.select_for_update().select_related("venue").get(
        pk=version_id
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
