from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
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
