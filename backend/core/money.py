from decimal import Decimal

from django.utils.formats import number_format


def format_ars_amount(amount: Decimal) -> str:
    """Format an ARS amount without hiding meaningful fractional digits.

    Decimal precision is preserved: zero fractional digits are omitted for whole
    pesos, while values containing cents are rendered with both decimal places.
    Negative amounts keep their sign before the currency symbol.
    """
    has_fractional_pesos = amount % 1 != 0
    formatted_amount = number_format(
        abs(amount),
        decimal_pos=2 if has_fractional_pesos else 0,
        use_l10n=True,
        force_grouping=True,
    )
    sign = "-" if amount < 0 else ""
    return f"{sign}$ {formatted_amount}"
