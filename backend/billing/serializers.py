from rest_framework import serializers

from academy.models import Student

from .models import ChargeAdjustment, MonthlyCharge


class FinancialStudentSerializer(serializers.ModelSerializer):
    firstName = serializers.CharField(source="first_name", read_only=True)
    lastName = serializers.CharField(source="last_name", read_only=True)
    accessType = serializers.SerializerMethodField(method_name="get_access_type")

    class Meta:
        model = Student
        fields = ("id", "firstName", "lastName", "accessType")

    def get_access_type(self, student):
        user = self.context["request"].user
        return "self" if student.user_id == user.pk else "guardian"


class ChargeAdjustmentReadSerializer(serializers.ModelSerializer):
    previousAmount = serializers.DecimalField(
        source="previous_amount", max_digits=12, decimal_places=2, read_only=True
    )
    resultingAmount = serializers.DecimalField(
        source="resulting_amount", max_digits=12, decimal_places=2, read_only=True
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = ChargeAdjustment
        fields = ("id", "previousAmount", "resultingAmount", "difference", "createdAt")


class MonthlyChargeReadSerializer(serializers.ModelSerializer):
    student = FinancialStudentSerializer(read_only=True)
    discipline = serializers.CharField(source="discipline.name", read_only=True)
    period = serializers.DateField(format="%Y-%m", read_only=True)
    amount = serializers.DecimalField(
        source="current_amount", max_digits=12, decimal_places=2, read_only=True
    )
    originalAmount = serializers.DecimalField(
        source="amount", max_digits=12, decimal_places=2, read_only=True
    )
    releasedAmount = serializers.DecimalField(
        source="released_amount", max_digits=12, decimal_places=2, read_only=True
    )
    adjustments = ChargeAdjustmentReadSerializer(many=True, read_only=True)
    status = serializers.SerializerMethodField()
    baseAmount = serializers.DecimalField(
        source="base_amount", max_digits=12, decimal_places=2, read_only=True
    )
    scholarshipPercentage = serializers.IntegerField(
        source="scholarship_percentage", read_only=True, allow_null=True
    )
    discountAmount = serializers.DecimalField(
        source="discount_amount", max_digits=12, decimal_places=2, read_only=True
    )
    paidAmount = serializers.DecimalField(
        source="paid_amount", max_digits=12, decimal_places=2, read_only=True
    )
    balance = serializers.SerializerMethodField()

    class Meta:
        model = MonthlyCharge
        fields = (
            "id",
            "student",
            "discipline",
            "period",
            "baseAmount",
            "scholarshipPercentage",
            "discountAmount",
            "amount",
            "originalAmount",
            "releasedAmount",
            "adjustments",
            "status",
            "paidAmount",
            "balance",
        )

    def get_balance(self, charge):
        return format(charge.outstanding, ".2f")

    def get_status(self, charge):
        if charge.current_amount == 0:
            return "adjusted_to_zero" if charge.adjustments.all() else "scholarship"
        return "paid" if charge.outstanding == 0 else "pending"
