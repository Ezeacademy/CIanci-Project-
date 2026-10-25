from rest_framework import serializers

from .models import Enrollment, Student


class AccessibleStudentSerializer(serializers.ModelSerializer):
    firstName = serializers.CharField(source="first_name", read_only=True)
    lastName = serializers.CharField(source="last_name", read_only=True)
    accessType = serializers.SerializerMethodField(method_name="get_access_type")

    class Meta:
        model = Student
        fields = ("id", "firstName", "lastName", "accessType")

    def get_access_type(self, student):
        request = self.context["request"]
        return "self" if student.user_id == request.user.pk else "guardian"


class EnrollmentDisciplineSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class EnrollmentSerializer(serializers.ModelSerializer):
    discipline = EnrollmentDisciplineSerializer(read_only=True)
    enrolledAt = serializers.DateField(source="enrolled_at", read_only=True)
    endedAt = serializers.DateField(source="ended_at", read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = ("id", "discipline", "enrolledAt", "endedAt", "status")

    def get_status(self, enrollment):
        return "history" if enrollment.ended_at else "active"
