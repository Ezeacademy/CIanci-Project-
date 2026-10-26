import re
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _

from billing.services import generate_monthly_charges


class Command(BaseCommand):
    help = _("Genera los cargos mensuales para un período calendario.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--period",
            required=True,
            help=_("Período calendario con formato YYYY-MM, por ejemplo 2026-10."),
        )

    def handle(self, *args, **options):
        period_argument = options["period"]
        if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", period_argument):
            raise CommandError(_("El período debe tener formato YYYY-MM."))

        try:
            year, month = map(int, period_argument.split("-"))
            billing_period = date(year, month, 1)
        except ValueError as exc:
            raise CommandError(_("El período indicado no es válido.")) from exc

        generation_result = generate_monthly_charges(
            billing_period=billing_period
        )
        for student_name, discipline_name in generation_result.missing_prices:
            self.stderr.write(
                self.style.WARNING(
                    _("Sin tarifa aplicable; se omitió el cargo: %(entry)s")
                    % {"entry": f"{student_name} — {discipline_name}"}
                )
            )
        for changed_enrollment in generation_result.eligibility_changed:
            self.stderr.write(
                self.style.WARNING(
                    _(
                        "La inscripción dejó de cubrir el período durante "
                        "la ejecución; se omitió: %(entry)s"
                    )
                    % {"entry": changed_enrollment}
                )
            )

        self.stdout.write(
            _(
                "Período %(period)s — creados: %(created)s; existentes: %(existing)s; "
                "omitidos: %(omitted)s."
            )
            % {
                "period": period_argument,
                "created": generation_result.created,
                "existing": generation_result.existing,
                "omitted": generation_result.omitted,
            }
        )

        if generation_result.missing_prices:
            raise CommandError(
                _("No se generaron %(count)s cargos por falta de tarifa aplicable.")
                % {"count": len(generation_result.missing_prices)}
            )
