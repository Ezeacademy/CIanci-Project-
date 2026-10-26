import re
from calendar import monthrange
from collections import defaultdict
from datetime import date

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from academy.models import Enrollment
from billing.models import DisciplinePrice, MonthlyCharge


class Command(BaseCommand):
    help = _("Genera los cargos mensuales para un período calendario.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--period",
            required=True,
            help=_("Período calendario con formato YYYY-MM, por ejemplo 2026-10."),
        )

    def handle(self, *args, **options):
        period_arg = options["period"]
        if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", period_arg):
            raise CommandError(_("El período debe tener formato YYYY-MM."))

        try:
            year, month = map(int, period_arg.split("-"))
            period = date(year, month, 1)
        except ValueError as exc:
            raise CommandError(_("El período indicado no es válido.")) from exc

        month_end = date(year, month, monthrange(year, month)[1])

        # A person with two enrollments for the same discipline in this month is
        # charged once; the most recently started enrollment is the source record.
        enrollments = list(
            Enrollment.objects.filter(enrolled_at__lte=month_end)
            .filter(Q(ended_at__isnull=True) | Q(ended_at__gte=period))
            .select_related("student", "discipline")
            .order_by("student_id", "discipline_id", "-enrolled_at", "-pk")
        )
        candidates = {}
        for enrollment in enrollments:
            key = (enrollment.student_id, enrollment.discipline_id)
            candidates.setdefault(key, enrollment)

        stats = {"created": 0, "existing": 0, "omitted": 0}
        missing_prices = []
        eligibility_changed = []

        if candidates:
            student_ids = {student_id for student_id, _ in candidates}
            discipline_ids = {discipline_id for _, discipline_id in candidates}
            existing = set(
                MonthlyCharge.objects.filter(
                    period=period,
                    student_id__in=student_ids,
                    discipline_id__in=discipline_ids,
                ).values_list("student_id", "discipline_id")
            )

            prices_by_discipline = defaultdict(list)
            prices = DisciplinePrice.objects.filter(
                discipline_id__in=discipline_ids,
                effective_month__lte=period,
            ).order_by("discipline_id", "-effective_month")
            for price in prices:
                prices_by_discipline[price.discipline_id].append(price.pk)

            for key, selected_enrollment in candidates.items():
                if key in existing:
                    stats["existing"] += 1
                    continue

                student_id, discipline_id = key
                try:
                    with transaction.atomic():
                        enrollment = (
                            Enrollment.objects.select_for_update()
                            .select_related("student", "discipline")
                            .get(pk=selected_enrollment.pk)
                        )
                        if enrollment.enrolled_at > month_end or (
                            enrollment.ended_at and enrollment.ended_at < period
                        ):
                            stats["omitted"] += 1
                            eligibility_changed.append(
                                f"{enrollment.student} — {enrollment.discipline}"
                            )
                            continue

                        if MonthlyCharge.objects.filter(
                            student_id=student_id,
                            discipline_id=discipline_id,
                            period=period,
                        ).exists():
                            stats["existing"] += 1
                            continue

                        price = None
                        for price_id in prices_by_discipline[discipline_id]:
                            candidate_price = (
                                DisciplinePrice.objects.select_for_update().get(
                                    pk=price_id
                                )
                            )
                            if (
                                candidate_price.discipline_id == discipline_id
                                and candidate_price.effective_month <= period
                            ):
                                price = candidate_price
                                break

                        if price is None:
                            stats["omitted"] += 1
                            missing_prices.append(
                                f"{enrollment.student} — {enrollment.discipline}"
                            )
                            continue

                        MonthlyCharge.objects.create(
                            student_id=student_id,
                            discipline_id=discipline_id,
                            enrollment=enrollment,
                            period=period,
                            price_applied=price,
                            amount=price.amount,
                            currency=price.currency,
                        )
                        stats["created"] += 1
                except IntegrityError:
                    # The unique constraint is the final guard if another
                    # generator created this student/discipline/period concurrently.
                    if MonthlyCharge.objects.filter(
                        student_id=student_id,
                        discipline_id=discipline_id,
                        period=period,
                    ).exists():
                        stats["existing"] += 1
                    else:
                        raise
                except ValidationError:
                    # Model validation can observe a concurrent insert before the
                    # database unique constraint is reached.
                    if MonthlyCharge.objects.filter(
                        student_id=student_id,
                        discipline_id=discipline_id,
                        period=period,
                    ).exists():
                        stats["existing"] += 1
                    else:
                        raise
                except Enrollment.DoesNotExist:
                    stats["omitted"] += 1
                    eligibility_changed.append(
                        f"{selected_enrollment.student} — "
                        f"{selected_enrollment.discipline}"
                    )

        for entry in missing_prices:
            self.stderr.write(
                self.style.WARNING(
                    _("Sin tarifa aplicable; se omitió el cargo: %(entry)s")
                    % {"entry": entry}
                )
            )
        for entry in eligibility_changed:
            self.stderr.write(
                self.style.WARNING(
                    _(
                        "La inscripción dejó de cubrir el período durante "
                        "la ejecución; "
                        "se omitió: %(entry)s"
                    )
                    % {"entry": entry}
                )
            )

        self.stdout.write(
            _(
                "Período %(period)s — creados: %(created)s; existentes: %(existing)s; "
                "omitidos: %(omitted)s."
            )
            % {"period": period_arg, **stats}
        )

        if missing_prices:
            raise CommandError(
                _("No se generaron %(count)s cargos por falta de tarifa aplicable.")
                % {"count": len(missing_prices)}
            )
