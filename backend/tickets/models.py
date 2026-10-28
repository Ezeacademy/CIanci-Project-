from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _


class Show(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Borrador")
        PUBLISHED = "published", _("Publicado")
        ARCHIVED = "archived", _("Archivado")

    title = models.CharField(_("Título"), max_length=180)
    description = models.TextField(_("Descripción"), blank=True)
    image_url = models.URLField(_("Imagen (URL HTTPS)"), blank=True)
    status = models.CharField(
        _("Estado"), max_length=12, choices=Status.choices, default=Status.DRAFT
    )
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_shows",
    )
    updated_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_shows",
    )
    created_at = models.DateTimeField(_("Creado"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Actualizado"), auto_now=True)

    class Meta:
        ordering = ("title", "pk")
        permissions = [
            ("manage_ticketing", "Can manage shows, functions, venues and seat maps")
        ]

    def clean(self):
        super().clean()
        if self.image_url and not self.image_url.lower().startswith("https://"):
            raise ValidationError(
                {"image_url": _("La imagen debe usar una URL HTTPS.")}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Venue(models.Model):
    name = models.CharField(_("Nombre"), max_length=160)
    location = models.CharField(_("Ubicación"), max_length=240, blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_ticket_venues",
    )
    created_at = models.DateTimeField(_("Creado"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Actualizado"), auto_now=True)
    updated_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_ticket_venues",
    )

    class Meta:
        ordering = ("name", "pk")
        constraints = [
            models.UniqueConstraint(Lower("name"), name="tickets_venue_name_ci_unique")
        ]

    def __str__(self):
        return self.name


class SeatMapVersion(models.Model):
    venue = models.ForeignKey(
        Venue, on_delete=models.PROTECT, related_name="map_versions"
    )
    version_number = models.PositiveIntegerField()
    created_at = models.DateTimeField(_("Creado"), auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_seat_map_versions",
    )
    updated_at = models.DateTimeField(_("Actualizado"), auto_now=True)
    updated_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_seat_map_versions",
    )

    class Meta:
        ordering = ("venue_id", "-version_number")
        constraints = [
            models.UniqueConstraint(
                fields=("venue", "version_number"),
                name="tickets_venue_map_version_unique",
            ),
        ]

    @property
    def is_frozen(self):
        return self.functions.exists()

    @property
    def capacity(self):
        return Seat.objects.filter(
            row__section__map_version=self, is_operational=True
        ).count()

    def __str__(self):
        return f"{self.venue} — versión {self.version_number}"


class SeatMapLayout(models.Model):
    map_version = models.OneToOneField(
        SeatMapVersion,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="layout",
    )
    width = models.PositiveSmallIntegerField(
        default=1200, validators=[MinValueValidator(200), MaxValueValidator(5000)]
    )
    height = models.PositiveSmallIntegerField(
        default=800, validators=[MinValueValidator(200), MaxValueValidator(5000)]
    )
    stage_x = models.PositiveSmallIntegerField(default=400)
    stage_y = models.PositiveSmallIntegerField(default=30)
    stage_width = models.PositiveSmallIntegerField(default=400)
    stage_height = models.PositiveSmallIntegerField(default=70)
    stage_label = models.CharField(max_length=80, default="ESCENARIO")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(width__gte=200, width__lte=5000),
                name="tickets_map_layout_width_bounds",
            ),
            models.CheckConstraint(
                condition=Q(height__gte=200, height__lte=5000),
                name="tickets_map_layout_height_bounds",
            ),
            models.CheckConstraint(
                condition=Q(stage_width__gte=1, stage_height__gte=1),
                name="tickets_map_stage_size_positive",
            ),
            models.CheckConstraint(
                condition=Q(map_version__isnull=False),
                name="tickets_map_layout_has_owner",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.map_version_id:
            raise ValidationError(
                {"map_version": _("La geometría debe tener un mapa asociado.")}
            )
        if self.stage_x + self.stage_width > self.width:
            raise ValidationError({"stage_width": _("El escenario excede el plano.")})
        if self.stage_y + self.stage_height > self.height:
            raise ValidationError({"stage_height": _("El escenario excede el plano.")})
        if self.map_version_id:
            _ensure_map_editable(self.map_version_id)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.map_version_id:
                SeatMapVersion.objects.select_for_update().get(pk=self.map_version_id)
                _ensure_map_editable(self.map_version_id)
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            if self.map_version_id:
                SeatMapVersion.objects.select_for_update().get(pk=self.map_version_id)
                _ensure_map_editable(self.map_version_id)
            return super().delete(*args, **kwargs)


class SeatSection(models.Model):
    map_version = models.ForeignKey(
        SeatMapVersion, on_delete=models.PROTECT, related_name="sections"
    )
    name = models.CharField(_("Sector"), max_length=100)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "name", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("map_version", "name"),
                name="tickets_section_name_per_map_unique",
            )
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        _ensure_map_editable(self.map_version_id)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        _ensure_map_editable(self.map_version_id)
        return super().delete(*args, **kwargs)


class SeatSectionLayout(models.Model):
    class Shape(models.TextChoices):
        RECTANGLE = "rectangle", _("Rectangular")
        ARC = "arc", _("Curvo")

    section = models.OneToOneField(
        SeatSection,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="layout",
    )
    shape = models.CharField(
        max_length=12, choices=Shape.choices, default=Shape.RECTANGLE
    )
    level_name = models.CharField(max_length=80, default="Planta principal")
    level_order = models.PositiveSmallIntegerField(default=0)
    x = models.PositiveSmallIntegerField(default=0)
    y = models.PositiveSmallIntegerField(default=0)
    width = models.PositiveSmallIntegerField(default=300)
    height = models.PositiveSmallIntegerField(default=220)
    rotation = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(359)]
    )
    inner_radius_ratio = models.DecimalField(
        max_digits=4, decimal_places=3, default=Decimal("0.55")
    )
    start_angle = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("205")
    )
    end_angle = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("335")
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(section__isnull=False),
                name="tickets_section_layout_has_owner",
            ),
            models.CheckConstraint(
                condition=Q(width__gte=1, height__gte=1),
                name="tickets_section_layout_size_positive",
            ),
            models.CheckConstraint(
                condition=Q(rotation__lte=359),
                name="tickets_section_layout_rotation_valid",
            ),
            models.CheckConstraint(
                condition=Q(inner_radius_ratio__gte=0, inner_radius_ratio__lt=1),
                name="tickets_section_inner_radius_valid",
            ),
            models.CheckConstraint(
                condition=Q(start_angle__gte=-360, start_angle__lte=360)
                & Q(end_angle__gte=-360, end_angle__lte=720)
                & Q(end_angle__gt=models.F("start_angle"))
                & Q(end_angle__lte=models.F("start_angle") + 360),
                name="tickets_section_arc_angles_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.section_id:
            raise ValidationError(
                {"section": _("La geometría debe tener un sector asociado.")}
            )
        map_version_id = self.section.map_version_id
        _ensure_map_editable(map_version_id)
        map_layout = getattr(self.section.map_version, "layout", None)
        canvas_width = map_layout.width if map_layout else 1200
        canvas_height = map_layout.height if map_layout else 800
        if self.x + self.width > canvas_width or self.y + self.height > canvas_height:
            raise ValidationError(
                {"width": _("El sector debe quedar dentro del plano del teatro.")}
            )

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.section_id:
                map_version_id = self.section.map_version_id
                SeatMapVersion.objects.select_for_update().get(pk=map_version_id)
                _ensure_map_editable(map_version_id)
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            if self.section_id:
                map_version_id = self.section.map_version_id
                SeatMapVersion.objects.select_for_update().get(pk=map_version_id)
                _ensure_map_editable(map_version_id)
            return super().delete(*args, **kwargs)


class SeatRow(models.Model):
    section = models.ForeignKey(
        SeatSection, on_delete=models.PROTECT, related_name="rows"
    )
    label = models.CharField(_("Fila"), max_length=24)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "label", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("section", "label"), name="tickets_row_label_per_section_unique"
            )
        ]

    def save(self, *args, **kwargs):
        _ensure_map_editable(self.section.map_version_id)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        _ensure_map_editable(self.section.map_version_id)
        return super().delete(*args, **kwargs)


class SeatRowLayout(models.Model):
    class Shape(models.TextChoices):
        STRAIGHT = "straight", _("Recta")
        ARC = "arc", _("En arco")

    row = models.OneToOneField(
        SeatRow,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="layout",
    )
    shape = models.CharField(
        max_length=8, choices=Shape.choices, default=Shape.STRAIGHT
    )
    start_x = models.PositiveSmallIntegerField(null=True, blank=True)
    start_y = models.PositiveSmallIntegerField(null=True, blank=True)
    end_x = models.PositiveSmallIntegerField(null=True, blank=True)
    end_y = models.PositiveSmallIntegerField(null=True, blank=True)
    center_x = models.PositiveSmallIntegerField(null=True, blank=True)
    center_y = models.PositiveSmallIntegerField(null=True, blank=True)
    radius_x = models.PositiveSmallIntegerField(null=True, blank=True)
    radius_y = models.PositiveSmallIntegerField(null=True, blank=True)
    start_angle = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    end_angle = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(row__isnull=False),
                name="tickets_row_layout_has_owner",
            ),
            models.CheckConstraint(
                condition=(
                    Q(shape="straight")
                    & Q(start_x__isnull=False)
                    & Q(start_y__isnull=False)
                    & Q(end_x__isnull=False)
                    & Q(end_y__isnull=False)
                )
                | (
                    Q(shape="arc")
                    & Q(center_x__isnull=False)
                    & Q(center_y__isnull=False)
                    & Q(radius_x__gt=0)
                    & Q(radius_y__gt=0)
                    & Q(start_angle__isnull=False)
                    & Q(end_angle__isnull=False)
                ),
                name="tickets_row_layout_geometry_present",
            ),
            models.CheckConstraint(
                condition=Q(start_angle__gte=-360, start_angle__lte=360)
                & Q(end_angle__gte=-360, end_angle__lte=720)
                & Q(end_angle__gt=models.F("start_angle"))
                & Q(end_angle__lte=models.F("start_angle") + 360),
                name="tickets_row_arc_angles_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.row_id:
            raise ValidationError(
                {"row": _("La geometría debe tener una fila asociada.")}
            )
        _ensure_map_editable(self.row.section.map_version_id)
        map_layout = getattr(self.row.section.map_version, "layout", None)
        canvas_width = map_layout.width if map_layout else 1200
        canvas_height = map_layout.height if map_layout else 800
        if self.shape == self.Shape.STRAIGHT:
            coordinates = (self.start_x, self.start_y, self.end_x, self.end_y)
            if any(value is None for value in coordinates):
                raise ValidationError(_("La fila recta necesita dos extremos."))
            if (
                all(
                    0 <= value <= canvas_limit
                    for value, canvas_limit in (
                        (self.start_x, canvas_width),
                        (self.end_x, canvas_width),
                        (self.start_y, canvas_height),
                        (self.end_y, canvas_height),
                    )
                )
                is False
            ):
                raise ValidationError(_("La fila debe quedar dentro del plano."))
        elif self.shape == self.Shape.ARC:
            arc_values = (
                self.center_x,
                self.center_y,
                self.radius_x,
                self.radius_y,
                self.start_angle,
                self.end_angle,
            )
            if any(value is None for value in arc_values):
                raise ValidationError(_("La fila en arco está incompleta."))
            if self.radius_x <= 0 or self.radius_y <= 0:
                raise ValidationError(_("El radio de la fila debe ser positivo."))
            if (
                self.end_angle <= self.start_angle
                or self.end_angle - self.start_angle > 360
            ):
                raise ValidationError(_("El arco debe cubrir como máximo 360 grados."))
            if (
                self.center_x + self.radius_x > canvas_width
                or self.center_y + self.radius_y > canvas_height
                or self.center_x - self.radius_x < 0
                or self.center_y - self.radius_y < 0
            ):
                raise ValidationError(_("La fila debe quedar dentro del plano."))

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.row_id:
                map_version_id = self.row.section.map_version_id
                SeatMapVersion.objects.select_for_update().get(pk=map_version_id)
                _ensure_map_editable(map_version_id)
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            if self.row_id:
                map_version_id = self.row.section.map_version_id
                SeatMapVersion.objects.select_for_update().get(pk=map_version_id)
                _ensure_map_editable(map_version_id)
            return super().delete(*args, **kwargs)


class Seat(models.Model):
    row = models.ForeignKey(SeatRow, on_delete=models.PROTECT, related_name="seats")
    number = models.CharField(_("Identificación"), max_length=24)
    position = models.PositiveSmallIntegerField()
    is_accessible = models.BooleanField(_("Accesible"), default=False)
    is_operational = models.BooleanField(_("Operativa"), default=True)

    class Meta:
        ordering = ("position", "pk")
        constraints = [
            models.CheckConstraint(
                condition=Q(position__gte=1), name="tickets_seat_position_positive"
            ),
            models.UniqueConstraint(
                fields=("row", "number"), name="tickets_seat_number_per_row_unique"
            ),
            models.UniqueConstraint(
                fields=("row", "position"), name="tickets_seat_position_per_row_unique"
            ),
        ]

    def clean(self):
        super().clean()
        if self.row_id:
            for gap in self.row.gaps.all():
                if gap.position <= self.position < gap.position + gap.width:
                    raise ValidationError(
                        {
                            "position": _(
                                "La butaca se superpone con un pasillo o espacio vacío."
                            )
                        }
                    )

    def save(self, *args, **kwargs):
        _ensure_map_editable(self.row.section.map_version_id)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        _ensure_map_editable(self.row.section.map_version_id)
        return super().delete(*args, **kwargs)


class SeatGap(models.Model):
    class Kind(models.TextChoices):
        AISLE = "aisle", _("Pasillo")
        EMPTY = "empty", _("Espacio vacío")

    row = models.ForeignKey(SeatRow, on_delete=models.PROTECT, related_name="gaps")
    position = models.PositiveSmallIntegerField()
    width = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1)]
    )
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.AISLE)

    class Meta:
        ordering = ("position", "pk")
        constraints = [
            models.CheckConstraint(
                condition=Q(position__gte=1), name="tickets_gap_position_positive"
            ),
            models.CheckConstraint(
                condition=Q(width__gte=1), name="tickets_gap_width_positive"
            ),
            models.UniqueConstraint(
                fields=("row", "position"), name="tickets_gap_position_per_row_unique"
            ),
        ]

    def clean(self):
        super().clean()
        if self.row_id and self.position is not None:
            gap_end = self.position + self.width
            seat_positions = self.row.seats.values_list("position", flat=True)
            if any(self.position <= position < gap_end for position in seat_positions):
                raise ValidationError(
                    {"position": _("El espacio se superpone con una butaca.")}
                )
            other_gaps = self.row.gaps.exclude(pk=self.pk)
            if any(
                self.position < gap.position + gap.width and gap.position < gap_end
                for gap in other_gaps
            ):
                raise ValidationError(
                    {"position": _("Los pasillos o espacios no pueden superponerse.")}
                )

    def save(self, *args, **kwargs):
        _ensure_map_editable(self.row.section.map_version_id)
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        _ensure_map_editable(self.row.section.map_version_id)
        return super().delete(*args, **kwargs)


class ShowFunction(models.Model):
    show = models.ForeignKey(Show, on_delete=models.PROTECT, related_name="functions")
    map_version = models.ForeignKey(
        SeatMapVersion, on_delete=models.PROTECT, related_name="functions"
    )
    starts_at = models.DateTimeField(_("Fecha y hora"))
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_show_functions",
    )
    updated_at = models.DateTimeField(_("Actualizado"), auto_now=True)
    updated_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_show_functions",
    )

    class Meta:
        ordering = ("starts_at", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("show", "starts_at"),
                name="tickets_show_function_datetime_unique",
            )
        ]

    def clean(self):
        super().clean()
        if self.map_version_id and self.map_version.venue_id is None:
            raise ValidationError(
                {"map_version": _("Seleccioná una versión válida del mapa.")}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def capacity(self):
        return self.map_version.capacity

    def __str__(self):
        return f"{self.show} — {self.starts_at:%d/%m/%Y %H:%M}"


class FunctionSectionPrice(models.Model):
    function = models.ForeignKey(
        ShowFunction, on_delete=models.PROTECT, related_name="section_prices"
    )
    section = models.ForeignKey(
        SeatSection, on_delete=models.PROTECT, related_name="function_prices"
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )

    class Meta:
        ordering = ("section__sort_order", "section__name")
        constraints = [
            models.UniqueConstraint(
                fields=("function", "section"),
                name="tickets_price_per_function_section_unique",
            )
        ]

    def clean(self):
        super().clean()
        if (
            self.function_id
            and self.section_id
            and self.function.map_version_id != self.section.map_version_id
        ):
            raise ValidationError(
                {"section": _("El sector debe pertenecer al mapa de esta función.")}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class TicketingDeletionAudit(models.Model):
    class EntityType(models.TextChoices):
        SHOW = "show", _("Espectáculo")
        FUNCTION = "function", _("Función")
        VENUE = "venue", _("Recinto")
        SEAT_MAP = "seat_map", _("Versión de mapa")

    entity_type = models.CharField(max_length=12, choices=EntityType.choices)
    object_id = models.PositiveBigIntegerField()
    object_label = models.CharField(max_length=240)
    deleted_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ticketing_deletion_audits",
    )
    deleted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ("view",)
        ordering = ("-deleted_at", "-pk")
        verbose_name = _("Registro de eliminación de ticketera")
        verbose_name_plural = _("Registros de eliminación de ticketera")

    def __str__(self):
        return f"{self.get_entity_type_display()}: {self.object_label}"


def _ensure_map_editable(map_version_id):
    if (
        map_version_id
        and SeatMapVersion.objects.filter(
            pk=map_version_id, functions__isnull=False
        ).exists()
    ):
        raise ValidationError(
            _(
                "Esta versión del mapa está asociada a una función. "
                "Creá una nueva versión para modificarla."
            )
        )
