from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import Count, Prefetch, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from adminpanel.permissions import has_admin_permission

from .layout import (
    map_layout_data,
    row_layout_data,
    row_slot_positions,
    section_layout_data,
)
from .models import (
    FunctionSectionPrice,
    SeatMapVersion,
    SeatRow,
    SeatSection,
    Show,
    ShowFunction,
    Venue,
)
from .services import (
    create_map_version,
    create_map_version_from,
    create_show_function,
    delete_seat_map_version,
    delete_show,
    delete_show_function,
    delete_venue,
    replace_map_structure,
    update_show_function,
)


class ShowInputSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=180, trim_whitespace=True)
    description = serializers.CharField(required=False, allow_blank=True)
    imageUrl = serializers.URLField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Show.Status.choices, required=False)

    def validate_imageUrl(self, value):
        if value and not value.lower().startswith("https://"):
            raise serializers.ValidationError("La imagen debe usar una URL HTTPS.")
        return value


class VenueInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160, trim_whitespace=True)
    location = serializers.CharField(max_length=240, required=False, allow_blank=True)

    def validate_name(self, value):
        matching_venues = Venue.objects.filter(name__iexact=value)
        if self.instance is not None:
            matching_venues = matching_venues.exclude(pk=self.instance.pk)
        if matching_venues.exists():
            raise serializers.ValidationError("Ya existe un recinto con ese nombre.")
        return value


class SeatInputSerializer(serializers.Serializer):
    number = serializers.CharField(max_length=24, trim_whitespace=True)
    position = serializers.IntegerField(min_value=1, max_value=32767)
    isAccessible = serializers.BooleanField(required=False, default=False)
    isOperational = serializers.BooleanField(required=False, default=True)


class GapInputSerializer(serializers.Serializer):
    position = serializers.IntegerField(min_value=1, max_value=32767)
    width = serializers.IntegerField(min_value=1, max_value=32767, default=1)
    kind = serializers.ChoiceField(choices=("aisle", "empty"), default="aisle")


class RowInputSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=24, trim_whitespace=True)
    sortOrder = serializers.IntegerField(min_value=0, max_value=32767, required=False)
    seats = SeatInputSerializer(many=True)
    gaps = GapInputSerializer(many=True, required=False, default=list)


class SectionInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, trim_whitespace=True)
    sortOrder = serializers.IntegerField(min_value=0, max_value=32767, required=False)
    rows = RowInputSerializer(many=True)


class SeatMapInputSerializer(serializers.Serializer):
    sections = SectionInputSerializer(many=True, allow_empty=False)


class FunctionPriceInputSerializer(serializers.Serializer):
    sectionId = serializers.IntegerField(min_value=1)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)


class FunctionInputSerializer(serializers.Serializer):
    mapVersionId = serializers.IntegerField(min_value=1)
    startsAt = serializers.DateTimeField()
    sectionPrices = FunctionPriceInputSerializer(many=True, required=False)


class FunctionUpdateInputSerializer(serializers.Serializer):
    startsAt = serializers.DateTimeField(required=False)
    sectionPrices = FunctionPriceInputSerializer(many=True, required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "Indicá qué dato de la función querés cambiar."
            )
        return attrs

    def validate_sectionPrices(self, prices):
        section_ids = [price["sectionId"] for price in prices]
        if len(section_ids) != len(set(section_ids)):
            raise serializers.ValidationError("No repitas sectores en los precios.")
        return prices


class TicketingAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    def require(self, permission):
        if not has_admin_permission(self.request.user, permission):
            raise PermissionDenied("No tenés permiso para realizar esta operación.")

    def require_management(self):
        self.require("tickets.manage_ticketing")


class PublicShowsView(APIView):
    """Expose published shows and upcoming functions without admin data."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        shows = _public_shows_queryset(include_map=False)
        return Response([_public_show_data(show) for show in shows])


class PublicShowDetailView(APIView):
    """Return one published show with its real seat-map layouts and prices."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, show_id):
        show = get_object_or_404(_public_shows_queryset(include_map=False), pk=show_id)
        data = _public_show_data(show)
        data["hasPastFunctions"] = ShowFunction.objects.filter(
            show=show, starts_at__lt=timezone.now()
        ).exists()
        return Response(data)


class PublicFunctionSeatMapView(APIView):
    """Expose a function's published seat map for local seat selection."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, show_id, function_id):
        function = get_object_or_404(
            _public_functions_queryset(include_map=True),
            pk=function_id,
            show_id=show_id,
            show__status=Show.Status.PUBLISHED,
            starts_at__gte=timezone.now(),
        )
        data = _public_function_data(function)
        data["sections"] = _legacy_public_section_data(function)
        return Response(data)


class PublicFunctionSeatMapOverviewView(APIView):
    """Return map geometry and seat counts without loading individual seats."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, show_id, function_id):
        function = get_object_or_404(
            _public_functions_queryset(include_map=False, include_layout=True),
            pk=function_id,
            show_id=show_id,
            show__status=Show.Status.PUBLISHED,
            starts_at__gte=timezone.now(),
        )
        sections = list(
            SeatSection.objects.filter(map_version_id=function.map_version_id)
            .select_related("layout")
            .annotate(
                operational_seat_count=Count(
                    "rows__seats",
                    filter=Q(rows__seats__is_operational=True),
                    distinct=True,
                ),
                row_count=Count("rows", distinct=True),
            )
        )
        return Response(_public_function_overview_data(function, sections))


class PublicFunctionSeatSectionView(APIView):
    """Return selectable seats for one section of a public upcoming function."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, show_id, function_id, section_id):
        function = get_object_or_404(
            _public_functions_queryset(include_map=False, include_layout=True),
            pk=function_id,
            show_id=show_id,
            show__status=Show.Status.PUBLISHED,
            starts_at__gte=timezone.now(),
        )
        ordered_section_ids = list(
            SeatSection.objects.filter(map_version_id=function.map_version_id)
            .order_by("sort_order", "name", "pk")
            .values_list("pk", flat=True)
        )
        section = get_object_or_404(
            SeatSection.objects.filter(map_version_id=function.map_version_id)
            .select_related("layout")
            .prefetch_related(
                Prefetch(
                    "rows",
                    queryset=SeatRow.objects.select_related("layout").prefetch_related(
                        "seats", "gaps"
                    ),
                )
            ),
            pk=section_id,
        )
        price = next(
            (
                section_price
                for section_price in function.section_prices.all()
                if section_price.section_id == section.pk
            ),
            None,
        )
        return Response(
            _public_function_section_data(
                function,
                section,
                price,
                section_index=ordered_section_ids.index(section.pk),
                section_count=len(ordered_section_ids),
            )
        )


class AdminShowsView(TicketingAPIView):
    def get(self, request):
        self.require("tickets.view_show")
        can_delete_show = has_admin_permission(request.user, "tickets.delete_show")
        can_delete_function = has_admin_permission(
            request.user, "tickets.delete_showfunction"
        )
        return Response(
            [
                _show_data(
                    show,
                    can_delete=can_delete_show,
                    can_delete_function=can_delete_function,
                )
                for show in Show.objects.prefetch_related(
                    Prefetch(
                        "functions",
                        queryset=_functions_with_capacity()
                        .select_related("map_version__venue")
                        .prefetch_related("section_prices__section"),
                    )
                )
            ]
        )

    def post(self, request):
        self.require_management()
        serializer = ShowInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        show = Show.objects.create(
            title=data["title"],
            description=data.get("description", ""),
            image_url=data.get("imageUrl", ""),
            status=data.get("status", Show.Status.DRAFT),
            created_by=request.user,
        )
        return Response(_show_data(show), status=201)


class AdminShowDetailView(TicketingAPIView):
    def patch(self, request, show_id):
        self.require_management()
        show = get_object_or_404(Show, pk=show_id)
        serializer = ShowInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        field_names = {"imageUrl": "image_url"}
        for field, value in serializer.validated_data.items():
            setattr(show, field_names.get(field, field), value)
        show.updated_by = request.user
        show.save()
        return Response(_show_data(show))

    def delete(self, request, show_id):
        self.require("tickets.delete_show")
        try:
            delete_show(show_id, request.user)
        except DjangoValidationError as error:
            return Response({"detail": error.messages}, status=409)
        except ProtectedError:
            return Response(
                {
                    "detail": (
                        "No se puede eliminar este espectáculo porque conserva "
                        "información vinculada. Archivarlo mantiene su historial."
                    )
                },
                status=409,
            )
        return Response(status=204)

    def post(self, request, show_id):
        self.require_management()
        show = get_object_or_404(Show, pk=show_id)
        serializer = FunctionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        version = get_object_or_404(SeatMapVersion, pk=data["mapVersionId"])
        if not version.sections.exists():
            raise serializers.ValidationError(
                {"mapVersionId": "El mapa todavía no tiene sectores."}
            )
        try:
            function = create_show_function(
                show=show,
                map_version=version,
                starts_at=data["startsAt"],
                section_prices=[
                    {"section_id": item["sectionId"], "amount": item["amount"]}
                    for item in data.get("sectionPrices", [])
                ],
                actor=request.user,
            )
        except (IntegrityError, DjangoValidationError, KeyError) as error:
            raise serializers.ValidationError(
                {
                    "detail": (
                        "No pudimos guardar la función. Revisá el mapa y los "
                        "precios por sector."
                    )
                }
            ) from error
        return Response(_function_data(function), status=201)


class AdminFunctionDetailView(TicketingAPIView):
    def patch(self, request, function_id):
        self.require_management()
        get_object_or_404(ShowFunction, pk=function_id)
        serializer = FunctionUpdateInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            function = update_show_function(
                function_id=function_id,
                actor=request.user,
                starts_at=data.get("startsAt"),
                section_prices=(
                    [
                        {
                            "section_id": price["sectionId"],
                            "amount": price["amount"],
                        }
                        for price in data["sectionPrices"]
                    ]
                    if "sectionPrices" in data
                    else None
                ),
            )
        except IntegrityError as error:
            raise serializers.ValidationError(
                {
                    "startsAt": (
                        "Ya existe otra función de este espectáculo en ese horario."
                    )
                }
            ) from error
        except DjangoValidationError as error:
            raise serializers.ValidationError({"detail": error.messages}) from error
        return Response(_function_data(function))

    def delete(self, request, function_id):
        self.require("tickets.delete_showfunction")
        try:
            delete_show_function(function_id, request.user)
        except ProtectedError:
            return Response(
                {
                    "detail": (
                        "No se puede eliminar esta función porque tiene reservas, "
                        "ventas o entradas vinculadas."
                    )
                },
                status=409,
            )
        return Response(status=204)


class AdminVenuesView(TicketingAPIView):
    def get(self, request):
        self.require("tickets.view_show")
        can_delete_venue = has_admin_permission(request.user, "tickets.delete_venue")
        can_delete_map = has_admin_permission(
            request.user, "tickets.delete_seatmapversion"
        )
        return Response(
            [
                _venue_data(
                    venue,
                    can_delete=can_delete_venue,
                    can_delete_map=can_delete_map,
                )
                for venue in Venue.objects.prefetch_related(
                    Prefetch("map_versions", queryset=_maps_with_totals())
                )
            ]
        )

    def post(self, request):
        self.require_management()
        serializer = VenueInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            venue = Venue.objects.create(
                **serializer.validated_data, created_by=request.user
            )
        except IntegrityError as error:
            raise serializers.ValidationError(
                {"name": "Ya existe un recinto con ese nombre."}
            ) from error
        return Response(_venue_data(venue), status=201)


class AdminVenueDetailView(TicketingAPIView):
    def patch(self, request, venue_id):
        self.require_management()
        venue = get_object_or_404(Venue, pk=venue_id)
        serializer = VenueInputSerializer(
            data=request.data, partial=True, instance=venue
        )
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(venue, field, value)
        venue.updated_by = request.user
        try:
            venue.save()
        except IntegrityError as error:
            raise serializers.ValidationError(
                {"name": "Ya existe un recinto con ese nombre."}
            ) from error
        return Response(_venue_data(venue))

    def delete(self, request, venue_id):
        self.require("tickets.delete_venue")
        try:
            delete_venue(venue_id, request.user)
        except DjangoValidationError as error:
            return Response({"detail": error.messages}, status=409)
        except ProtectedError:
            return Response(
                {
                    "detail": (
                        "No se puede eliminar el recinto porque tiene registros "
                        "vinculados."
                    )
                },
                status=409,
            )
        return Response(status=204)


class AdminVenueMapView(TicketingAPIView):
    def get(self, request, venue_id):
        self.require("tickets.view_show")
        venue = get_object_or_404(Venue, pk=venue_id)
        return Response(
            {
                "venue": {
                    "id": venue.pk,
                    "name": venue.name,
                    "location": venue.location,
                },
                "versions": [
                    _map_data(
                        version,
                        include_sections=False,
                        can_delete=has_admin_permission(
                            request.user, "tickets.delete_seatmapversion"
                        ),
                    )
                    for version in _maps_with_totals().filter(venue=venue)
                ],
            }
        )

    def post(self, request, venue_id):
        self.require_management()
        get_object_or_404(Venue, pk=venue_id)
        source_id = request.data.get("copyVersionId")
        if source_id:
            source = get_object_or_404(SeatMapVersion, pk=source_id, venue_id=venue_id)
            version = create_map_version_from(source.pk, request.user)
        else:
            serializer = SeatMapInputSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            try:
                version = create_map_version(
                    venue_id, request.user, serializer.validated_data["sections"]
                )
            except (
                DjangoValidationError,
                IntegrityError,
                KeyError,
                TypeError,
            ) as error:
                raise serializers.ValidationError(
                    {"detail": "Revisá los sectores, filas y posiciones de butacas."}
                ) from error
        return Response(_map_data(version), status=201)


class AdminSeatMapDetailView(TicketingAPIView):
    def get(self, request, map_version_id):
        self.require("tickets.view_show")
        version = get_object_or_404(
            _maps_with_totals().prefetch_related(
                "sections__rows__seats", "sections__rows__gaps"
            ),
            pk=map_version_id,
        )
        return Response(
            _map_data(
                version,
                can_delete=has_admin_permission(
                    request.user, "tickets.delete_seatmapversion"
                ),
            )
        )

    def put(self, request, map_version_id):
        self.require_management()
        get_object_or_404(SeatMapVersion, pk=map_version_id)
        serializer = SeatMapInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            version = replace_map_structure(
                map_version_id,
                serializer.validated_data["sections"],
                actor=request.user,
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError({"detail": error.messages}) from error
        except (IntegrityError, KeyError, TypeError) as error:
            raise serializers.ValidationError(
                {
                    "detail": (
                        "No pudimos guardar el mapa. Revisá la distribución y "
                        "probá nuevamente."
                    )
                }
            ) from error
        return Response(_map_data(version))

    def delete(self, request, map_version_id):
        self.require("tickets.delete_seatmapversion")
        try:
            delete_seat_map_version(map_version_id, request.user)
        except DjangoValidationError as error:
            return Response({"detail": error.messages}, status=409)
        except ProtectedError:
            return Response(
                {
                    "detail": (
                        "No se puede eliminar esta versión porque conserva "
                        "funciones o información comercial vinculada."
                    )
                },
                status=409,
            )
        return Response(status=204)


def _show_data(show, *, can_delete=False, can_delete_function=False):
    return {
        "id": show.pk,
        "title": show.title,
        "description": show.description,
        "imageUrl": show.image_url,
        "status": show.status,
        "canDelete": can_delete,
        "functions": [
            _function_data(function, can_delete=can_delete_function)
            for function in show.functions.all()
        ],
    }


def _function_data(function, *, can_delete=False):
    return {
        "id": function.pk,
        "startsAt": function.starts_at.isoformat(),
        "venue": function.map_version.venue.name,
        "mapVersionId": function.map_version_id,
        "capacity": (
            function.operational_capacity
            if hasattr(function, "operational_capacity")
            else function.capacity
        ),
        "canDelete": can_delete,
        "sectionPrices": [
            {
                "sectionId": price.section_id,
                "section": price.section.name,
                "amount": str(price.amount),
            }
            for price in function.section_prices.all()
        ],
    }


def _venue_data(venue, *, can_delete=False, can_delete_map=False):
    return {
        "id": venue.pk,
        "name": venue.name,
        "location": venue.location,
        "canDelete": can_delete,
        "versions": [
            _map_data(
                version,
                include_sections=False,
                can_delete=can_delete_map,
            )
            for version in venue.map_versions.all()
        ],
    }


def _map_data(version, include_sections=True, *, can_delete=False):
    data = {
        "id": version.pk,
        "venueId": version.venue_id,
        "venue": version.venue.name,
        "version": version.version_number,
        "capacity": (
            version.operational_capacity
            if hasattr(version, "operational_capacity")
            else version.capacity
        ),
        "isFrozen": (
            version.function_count > 0
            if hasattr(version, "function_count")
            else version.is_frozen
        ),
        "canDelete": can_delete,
    }
    if include_sections:
        data["sections"] = []
        for section in version.sections.prefetch_related("rows__seats", "rows__gaps"):
            data["sections"].append(
                {
                    "id": section.pk,
                    "name": section.name,
                    "sortOrder": section.sort_order,
                    "rows": [
                        {
                            "id": row.pk,
                            "label": row.label,
                            "sortOrder": row.sort_order,
                            "seats": [
                                {
                                    "id": seat.pk,
                                    "number": seat.number,
                                    "position": seat.position,
                                    "isAccessible": seat.is_accessible,
                                    "isOperational": seat.is_operational,
                                }
                                for seat in row.seats.all()
                            ],
                            "gaps": [
                                {
                                    "position": gap.position,
                                    "width": gap.width,
                                    "kind": gap.kind,
                                }
                                for gap in row.gaps.all()
                            ],
                        }
                        for row in section.rows.all()
                    ],
                }
            )
    return data


def _functions_with_capacity():
    return ShowFunction.objects.annotate(
        operational_capacity=Count(
            "map_version__sections__rows__seats",
            filter=Q(map_version__sections__rows__seats__is_operational=True),
            distinct=True,
        )
    )


def _maps_with_totals():
    return SeatMapVersion.objects.annotate(
        operational_capacity=Count(
            "sections__rows__seats",
            filter=Q(sections__rows__seats__is_operational=True),
            distinct=True,
        ),
        function_count=Count("functions", distinct=True),
    ).select_related("venue")


def _public_functions_queryset(*, include_map, include_layout=False):
    function_queryset = (
        ShowFunction.objects.filter(starts_at__gte=timezone.now())
        .select_related("map_version__venue")
        .annotate(
            operational_capacity=Count(
                "map_version__sections__rows__seats",
                filter=Q(map_version__sections__rows__seats__is_operational=True),
                distinct=True,
            )
        )
        .prefetch_related(
            Prefetch(
                "section_prices",
                queryset=FunctionSectionPrice.objects.select_related("section"),
            )
        )
    )
    if include_layout:
        function_queryset = function_queryset.select_related("map_version__layout")
    if include_map:
        function_queryset = function_queryset.prefetch_related(
            Prefetch(
                "map_version__sections",
                queryset=SeatSection.objects.prefetch_related(
                    "rows__seats", "rows__gaps"
                ),
            )
        )
    return function_queryset


def _public_shows_queryset(*, include_map):
    return Show.objects.filter(status=Show.Status.PUBLISHED).prefetch_related(
        Prefetch(
            "functions",
            queryset=_public_functions_queryset(include_map=include_map),
        )
    )


def _public_show_data(show):
    return {
        "id": show.pk,
        "title": show.title,
        "description": show.description,
        "imageUrl": show.image_url,
        "functions": [
            _public_function_data(function) for function in show.functions.all()
        ],
    }


def _public_function_data(function):
    data = {
        "id": function.pk,
        "startsAt": function.starts_at.isoformat(),
        "venue": function.map_version.venue.name,
        "location": function.map_version.venue.location,
        "capacity": function.operational_capacity,
        "sectionPrices": [
            {
                "section": price.section.name,
                "amount": str(price.amount),
            }
            for price in function.section_prices.all()
        ],
    }
    return data


def _legacy_public_section_data(function):
    """Keep the original full-map response stable for existing consumers."""
    prices_by_section = {
        price.section_id: str(price.amount) for price in function.section_prices.all()
    }
    return [
        {
            "name": section.name,
            "sortOrder": section.sort_order,
            "price": prices_by_section.get(section.pk),
            "rows": [
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
                        {
                            "position": gap.position,
                            "width": gap.width,
                            "kind": gap.kind,
                        }
                        for gap in row.gaps.all()
                    ],
                }
                for row in section.rows.all()
            ],
        }
        for section in function.map_version.sections.all()
    ]


def _public_section_map_data(
    section, price, *, section_index: int = 0, section_count: int = 1
):
    """Serialize a normalized section and its projected visual seat positions."""
    rows = list(section.rows.all())
    section_geometry = section_layout_data(
        section,
        section_index=section_index,
        section_count=section_count,
        row_count=len(rows),
    )
    serialized_rows = []
    for row_index, row in enumerate(rows):
        row_geometry = row_layout_data(
            row,
            section_layout=section_geometry,
            row_index=row_index,
            row_count=len(rows),
        )
        seats = list(row.seats.all())
        gaps = list(row.gaps.all())
        max_position = max(
            [seat.position for seat in seats]
            + [gap.position + gap.width - 1 for gap in gaps]
            + [1]
        )
        positions = row_slot_positions(
            row, max_position=max_position, geometry=row_geometry
        )
        serialized_rows.append(
            {
                "label": row.label,
                "sortOrder": row.sort_order,
                "layout": row_geometry,
                "seats": [
                    {
                        "number": seat.number,
                        "position": seat.position,
                        "isAccessible": seat.is_accessible,
                        "isOperational": seat.is_operational,
                        "visual": _slot_visual(positions[seat.position]),
                    }
                    for seat in seats
                ],
                "gaps": [
                    {
                        "position": gap.position,
                        "width": gap.width,
                        "kind": gap.kind,
                        "visual": _slot_visual(
                            positions[gap.position + (gap.width - 1) / 2]
                        ),
                    }
                    for gap in gaps
                ],
            }
        )
    return {
        "id": section.pk,
        "name": section.name,
        "sortOrder": section.sort_order,
        "price": price,
        "layout": section_geometry,
        "rows": serialized_rows,
    }


def _public_function_overview_data(function, sections):
    """Serialize section geometry and counts without loading individual seats."""
    prices_by_section = {
        price.section_id: str(price.amount) for price in function.section_prices.all()
    }
    return {
        "id": function.pk,
        "startsAt": function.starts_at.isoformat(),
        "venue": function.map_version.venue.name,
        "location": function.map_version.venue.location,
        "capacity": function.operational_capacity,
        "sectionPrices": [
            {"section": price.section.name, "amount": str(price.amount)}
            for price in function.section_prices.all()
        ],
        "layout": map_layout_data(function.map_version),
        "sections": [
            {
                "id": section.pk,
                "name": section.name,
                "sortOrder": section.sort_order,
                "price": prices_by_section.get(section.pk),
                "operationalSeatCount": section.operational_seat_count,
                "layout": section_layout_data(
                    section,
                    section_index=index,
                    section_count=len(sections),
                    row_count=section.row_count,
                ),
            }
            for index, section in enumerate(sections)
        ],
    }


def _public_function_section_data(
    function, section, price, *, section_index: int, section_count: int
):
    data = _public_section_map_data(
        section,
        str(price.amount) if price else None,
        section_index=section_index,
        section_count=max(1, section_count),
    )
    data["functionId"] = function.pk
    data["canvas"] = map_layout_data(function.map_version)
    return data


def _slot_visual(position):
    x, y, rotation = position
    return {"x": x, "y": y, "rotation": rotation}
