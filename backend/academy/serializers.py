from rest_framework import serializers

from .models import ClassSchedule, Discipline, Enrollment, Student, Teacher
from .schedules import get_next_class_occurrence


class PublicDisciplineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discipline
        fields = ("id", "name")
        read_only_fields = fields


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


class CalendarTeacherSerializer(serializers.ModelSerializer):
    firstName = serializers.CharField(source="first_name", read_only=True)
    lastName = serializers.CharField(source="last_name", read_only=True)

    class Meta:
        model = Teacher
        fields = ("firstName", "lastName")


class ClassScheduleSerializer(serializers.ModelSerializer):
    teacher = CalendarTeacherSerializer(read_only=True)
    weekdayName = serializers.CharField(source="get_weekday_display", read_only=True)
    startTime = serializers.TimeField(
        source="start_time", format="%H:%M", read_only=True
    )
    endTime = serializers.TimeField(source="end_time", format="%H:%M", read_only=True)
    nextClass = serializers.SerializerMethodField(method_name="get_next_class")

    class Meta:
        model = ClassSchedule
        fields = (
            "id",
            "weekday",
            "weekdayName",
            "startTime",
            "endTime",
            "teacher",
            "nextClass",
        )

    def get_next_class(self, schedule):
        return get_next_class_occurrence(
            schedule, not_before=self.context.get("enrollment_start")
        )


class CalendarEnrollmentSerializer(serializers.ModelSerializer):
    student = AccessibleStudentSerializer(read_only=True)
    discipline = EnrollmentDisciplineSerializer(read_only=True)
    schedules = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = ("id", "student", "discipline", "schedules")

    def get_schedules(self, enrollment):
        return ClassScheduleSerializer(
            enrollment.discipline.class_schedules.all(),
            many=True,
            context={"enrollment_start": enrollment.enrolled_at},
        ).data
