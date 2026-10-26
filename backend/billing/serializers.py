from rest_framework import serializers

from academy.models import Student

from .models import MonthlyCharge


class FinancialStudentSerializer(serializers.ModelSerializer):
    firstName = serializers.CharField(source="first_name", read_only=True)
    lastName = serializers.CharField(source="last_name", read_only=True)
    accessType = serializers.SerializerMethodField(method_name="get_access_type")

    class Meta:
        model = Student
        fields = ("firstName", "lastName", "accessType")

    def get_access_type(self, student):
        user = self.context["request"].user
        return "self" if student.user_id == user.pk else "guardian"


class MonthlyChargeReadSerializer(serializers.ModelSerializer):
    student = FinancialStudentSerializer(read_only=True)
    discipline = serializers.CharField(source="discipline.name", read_only=True)
    period = serializers.DateField(format="%Y-%m", read_only=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    paidAmount = serializers.DecimalField(
        source="paid_amount", max_digits=12, decimal_places=2, read_only=True
    )
    balance = serializers.SerializerMethodField()

    class Meta:
        model = MonthlyCharge
        fields = (
            "student",
            "discipline",
            "period",
            "amount",
            "paidAmount",
            "balance",
        )

    def get_balance(self, charge):
        return format(charge.amount - charge.paid_amount, ".2f")
