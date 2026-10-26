from rest_framework import serializers

from academy.models import Student

from .models import Payment, PaymentAllocation, PaymentIntent


class PaymentStudentSerializer(serializers.ModelSerializer):
    firstName = serializers.CharField(source="first_name", read_only=True)
    lastName = serializers.CharField(source="last_name", read_only=True)
    accessType = serializers.SerializerMethodField(method_name="get_access_type")

    class Meta:
        model = Student
        fields = ("firstName", "lastName", "accessType")

    def get_access_type(self, student):
        user = self.context["request"].user
        return "self" if student.user_id == user.pk else "guardian"


class PaymentAllocationReadSerializer(serializers.ModelSerializer):
    period = serializers.DateField(
        source="charge.period", format="%Y-%m", read_only=True
    )
    discipline = serializers.CharField(source="charge.discipline.name", read_only=True)

    class Meta:
        model = PaymentAllocation
        fields = ("period", "discipline", "amount")


class PaymentReadSerializer(serializers.ModelSerializer):
    student = PaymentStudentSerializer(read_only=True)
    receivedAt = serializers.DateTimeField(source="received_at", read_only=True)
    allocations = PaymentAllocationReadSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = (
            "student",
            "amount",
            "currency",
            "method",
            "receivedAt",
            "allocations",
        )


class PaymentIntentReadSerializer(serializers.ModelSerializer):
    student = PaymentStudentSerializer(read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = PaymentIntent
        fields = (
            "student",
            "amount",
            "currency",
            "method",
            "status",
            "createdAt",
        )
