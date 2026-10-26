from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from academy.models import Discipline, Enrollment, Student
from billing.models import DisciplinePrice, MonthlyCharge
from payments.models import Payment, PaymentAllocation, PaymentIntent


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class PaymentsAdminTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            "admin@example.com", "Safe-admin-password-92!"
        )
        self.client = Client()
        self.client.force_login(self.admin_user)
        self.student = Student.objects.create(first_name="Cande", last_name="Manzo")
        self.discipline = Discipline.objects.create(name="Jazz")
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            discipline=self.discipline,
            enrolled_at=date(2026, 9, 1),
        )
        self.price = DisciplinePrice.objects.create(
            discipline=self.discipline,
            amount=Decimal("30000.00"),
            effective_month=date(2026, 9, 1),
        )
        self.charge = MonthlyCharge.objects.create(
            student=self.student,
            discipline=self.discipline,
            enrollment=self.enrollment,
            period=date(2026, 9, 1),
            price_applied=self.price,
            amount=self.price.amount,
        )

    def test_cash_admin_flow_registers_and_allocates_partial_payment(self):
        url = reverse("admin:payments_payment_record_cash")
        form_data = {
            "student": self.student.pk,
            "amount": "12000.00",
            "received_at": "2026-10-25T12:30",
            "reference": "Caja 1",
        }

        response = self.client.post(url, {**form_data, "_load_charges": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Saldo disponible: $30000.00 ARS")

        response = self.client.post(
            url,
            {
                **form_data,
                f"charge_{self.charge.pk}": "12000.00",
                "_confirm_payment": "1",
            },
        )

        self.assertEqual(response.status_code, 302)
        payment = Payment.objects.get()
        self.assertEqual(payment.method, Payment.Method.CASH)
        self.assertEqual(payment.confirmed_by, self.admin_user)
        self.assertEqual(payment.allocations.get().charge_id, self.charge.pk)
        self.assertEqual(payment.amount, payment.allocated_amount)

    def test_transfer_admin_flow_keeps_pending_until_confirmed_and_assigned(self):
        add_url = reverse("admin:payments_paymentintent_add")
        response = self.client.post(
            add_url,
            {
                "student": self.student.pk,
                "amount": "10000.00",
                "reference": "Transferencia informada",
            },
        )
        self.assertEqual(response.status_code, 302)
        intent = PaymentIntent.objects.get()
        self.assertEqual(intent.status, PaymentIntent.Status.PENDING)
        self.assertEqual(intent.created_by, self.admin_user)
        self.assertFalse(Payment.objects.exists())

        confirm_url = reverse("admin:payments_paymentintent_confirm", args=(intent.pk,))
        self.assertEqual(self.client.get(confirm_url).status_code, 200)
        response = self.client.post(
            confirm_url,
            {f"charge_{self.charge.pk}": "10000.00"},
        )

        self.assertEqual(response.status_code, 302)
        intent.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.Status.CONFIRMED)
        payment = Payment.objects.get(intent=intent)
        self.assertEqual(payment.confirmed_by, self.admin_user)
        self.assertEqual(payment.allocated_amount, intent.amount)

    def test_overpayment_transfer_remains_pending_in_admin(self):
        intent = PaymentIntent.objects.create(
            student=self.student,
            amount=Decimal("31000.00"),
            created_by=self.admin_user,
        )
        confirm_url = reverse("admin:payments_paymentintent_confirm", args=(intent.pk,))

        response = self.client.post(
            confirm_url,
            {f"charge_{self.charge.pk}": "31000.00"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "supera la deuda disponible")
        intent.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.Status.PENDING)
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(PaymentAllocation.objects.exists())

    def test_authorized_admin_can_reject_pending_transfer(self):
        intent = PaymentIntent.objects.create(
            student=self.student,
            amount=Decimal("10000.00"),
            created_by=self.admin_user,
        )

        response = self.client.post(
            reverse("admin:payments_paymentintent_changelist"),
            {
                "action": "reject_selected_transfers",
                "_selected_action": [intent.pk],
                "index": "0",
            },
        )

        self.assertEqual(response.status_code, 302)
        intent.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.Status.REJECTED)
        self.assertEqual(intent.decided_by, self.admin_user)

    def test_payment_admin_uses_standard_permissions_for_confirmation(self):
        intent = PaymentIntent.objects.create(
            student=self.student,
            amount=Decimal("10000.00"),
            created_by=self.admin_user,
        )
        staff = get_user_model().objects.create_user(
            "staff@example.com", "Safe-admin-password-93!", is_staff=True
        )
        self.client.force_login(staff)

        response = self.client.get(
            reverse("admin:payments_paymentintent_confirm", args=(intent.pk,))
        )

        self.assertEqual(response.status_code, 403)
        intent.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.Status.PENDING)

    def test_view_only_staff_cannot_reject_a_transfer(self):
        intent = PaymentIntent.objects.create(
            student=self.student,
            amount=Decimal("10000.00"),
            created_by=self.admin_user,
        )
        staff = get_user_model().objects.create_user(
            "viewer@example.com", "Safe-admin-password-94!", is_staff=True
        )
        view_permission = Permission.objects.get(
            content_type__app_label="payments",
            codename="view_paymentintent",
        )
        staff.user_permissions.add(view_permission)
        self.client.force_login(staff)
        changelist = reverse("admin:payments_paymentintent_changelist")

        response = self.client.post(
            changelist,
            {
                "action": "reject_selected_transfers",
                "_selected_action": [intent.pk],
                "index": "0",
            },
        )

        self.assertEqual(response.status_code, 200)
        intent.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.Status.PENDING)
