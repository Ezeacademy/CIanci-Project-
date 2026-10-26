from decimal import Decimal

from django.test import SimpleTestCase, override_settings

from core.money import format_ars_amount


@override_settings(LANGUAGE_CODE="es-ar", USE_THOUSAND_SEPARATOR=True)
class FormatArsAmountTests(SimpleTestCase):
    def test_formats_whole_pesos_without_fractional_zeroes(self):
        self.assertEqual(format_ars_amount(Decimal("105000.00")), "$ 105.000")
        self.assertEqual(
            format_ars_amount(Decimal("9876543210.00")), "$ 9.876.543.210"
        )
        self.assertEqual(format_ars_amount(Decimal("0.00")), "$ 0")

    def test_preserves_meaningful_cents(self):
        self.assertEqual(format_ars_amount(Decimal("30000.50")), "$ 30.000,50")
        self.assertEqual(format_ars_amount(Decimal("1250.25")), "$ 1.250,25")

    def test_formats_negative_amounts_without_losing_cents(self):
        self.assertEqual(format_ars_amount(Decimal("-1250.25")), "-$ 1.250,25")
