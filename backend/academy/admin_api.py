"""Private API views for staff managing students and enrollments."""

from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.invitations import (
    InvitationAlreadyPending,
    issue_student_invitation,
    revoke_student_account_link,
    revoke_student_invitation,
    send_student_invitation_email,
)
from accounts.models import AccountInvitation, GuardianRelationship
from adminpanel.permissions import has_admin_permission

from .models import Discipline, Enrollment, Student
from .services import create_enrollment, create_student, finish_enrollment


class StudentInputSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, trim_whitespace=True)
    last_name = serializers.CharField(max_length=150, trim_whitespace=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)

    def to_internal_value(self, data):
        allowed_fields = {"first_name", "last_name", "date_of_birth"}
        unexpected_fields = set(data) - allowed_fields
        if unexpected_fields:
            raise serializers.ValidationError(
                {
                    field: "Este dato no se puede modificar desde esta pantalla."
                    for field in unexpected_fields
                }
            )
        return super().to_internal_value(data)


class EnrollmentInputSerializer(serializers.Serializer):
    discipline_id = serializers.IntegerField(min_value=1)
    enrolled_at = serializers.DateField()


class StudentInvitationInputSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254, trim_whitespace=True)


class StudentAdminPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


class AdminAcademicAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    def require_permissions(self, *permissions):
        if not all(
            has_admin_permission(self.request.user, permission)
            for permission in permissions
        ):
            raise PermissionDenied("No tenés permiso para realizar esta operación.")


class AdminStudentListCreateView(AdminAcademicAPIView):
    def get(self, request):
        self.require_permissions(
            "academy.view_student",
            "academy.view_enrollment",
            "academy.view_discipline",
        )
        students = Student.objects.annotate(
            active_enrollment_count=Count(
                "enrollments",
                filter=Q(enrollments__ended_at__isnull=True),
                distinct=True,
            )
        ).prefetch_related(
            Prefetch(
                "enrollments",
                queryset=Enrollment.objects.filter(ended_at__isnull=True)
                .select_related("discipline")
                .order_by("discipline__name", "pk"),
                to_attr="active_enrollments",
            )
        )

        search = request.query_params.get("q", "").strip()
        for search_word in search.split()[:5]:
            students = students.filter(
                Q(first_name__icontains=search_word)
                | Q(last_name__icontains=search_word)
            )

        status = request.query_params.get("status", "all")
        if status == "active":
            students = students.filter(active_enrollment_count__gt=0)
        elif status == "inactive":
            students = students.filter(active_enrollment_count=0)
        elif status != "all":
            raise ValidationError({"status": "Elegí un estado válido."})

        discipline_id = request.query_params.get("discipline")
        if discipline_id:
            if not discipline_id.isdecimal():
                raise ValidationError({"discipline": "Elegí una disciplina válida."})
            students = students.filter(
                enrollments__discipline_id=int(discipline_id),
                enrollments__ended_at__isnull=True,
            )

        students = students.order_by("last_name", "first_name", "pk")
        paginator = StudentAdminPagination()
        page = paginator.paginate_queryset(students, request, view=self)
        results = [
            {
                "id": student.pk,
                "firstName": student.first_name,
                "lastName": student.last_name,
                "activeEnrollmentCount": student.active_enrollment_count,
                "disciplines": [
                    enrollment.discipline.name
                    for enrollment in student.active_enrollments
                ],
            }
            for student in page
        ]
        response = paginator.get_paginated_response(results)
        response.data["filters"] = {
            "disciplines": list(
                Discipline.objects.order_by("name").values("id", "name")
            ),
            "canAddStudent": has_admin_permission(request.user, "academy.add_student"),
        }
        return response

    def post(self, request):
        self.require_permissions("academy.add_student")
        serializer = StudentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                student = create_student(**serializer.validated_data)
                _log_student(
                    request, student, ADDITION, "Alumno registrado desde el panel."
                )
        except DjangoValidationError as error:
            raise ValidationError(_validation_errors(error)) from error
        return Response(
            {
                "id": student.pk,
                "canInviteStudentAccount": has_admin_permission(
                    request.user, "academy.invite_student_account"
                ),
            },
            status=201,
        )


class AdminStudentDetailView(AdminAcademicAPIView):
    def get(self, request, student_id):
        self.require_permissions(
            "academy.view_student",
            "academy.view_enrollment",
            "academy.view_discipline",
        )
        student = get_object_or_404(Student, pk=student_id)
        enrollments = list(
            student.enrollments.select_related("discipline").order_by(
                "-enrolled_at", "-pk"
            )
        )
        guardians = []
        if has_admin_permission(request.user, "accounts.view_guardianrelationship"):
            relationships = (
                GuardianRelationship.objects.filter(student=student)
                .select_related("guardian")
                .order_by("-revoked_at", "guardian__last_name", "guardian__first_name")
            )
            guardians = [
                {
                    "name": str(relationship.guardian.get_full_name()).strip()
                    or "Tutor/a",
                    "isActive": relationship.revoked_at is None,
                }
                for relationship in relationships
            ]

        can_invite_student_account = has_admin_permission(
            request.user, "academy.invite_student_account"
        )
        can_revoke_student_account = has_admin_permission(
            request.user, "academy.revoke_student_account"
        )
        account_access = None
        if can_invite_student_account or can_revoke_student_account:
            latest_invitation = (
                AccountInvitation.objects.filter(
                    student=student,
                    consumed_at__isnull=True,
                    revoked_at__isnull=True,
                )
                .order_by("-created_at", "-pk")
                .first()
            )
            if student.user_id is not None:
                account_access = {
                    "status": "linked",
                    "email": student.user.email,
                    "expiresAt": None,
                    "invitationId": None,
                }
            elif latest_invitation is None:
                account_access = {
                    "status": "none",
                    "email": None,
                    "expiresAt": None,
                    "invitationId": None,
                }
            elif latest_invitation.expires_at <= timezone.now():
                account_access = {
                    "status": "expired",
                    "email": latest_invitation.email,
                    "expiresAt": latest_invitation.expires_at,
                    "invitationId": latest_invitation.pk,
                }
            else:
                account_access = {
                    "status": "pending",
                    "email": latest_invitation.email,
                    "expiresAt": latest_invitation.expires_at,
                    "invitationId": latest_invitation.pk,
                }

        return Response(
            {
                "id": student.pk,
                "today": timezone.localdate(),
                "firstName": student.first_name,
                "lastName": student.last_name,
                "dateOfBirth": student.date_of_birth,
                "activeEnrollmentCount": sum(
                    enrollment.ended_at is None for enrollment in enrollments
                ),
                "enrollments": [
                    {
                        "id": enrollment.pk,
                        "discipline": enrollment.discipline.name,
                        "disciplineIsActive": enrollment.discipline.is_active,
                        "enrolledAt": enrollment.enrolled_at,
                        "endedAt": enrollment.ended_at,
                        "isActive": enrollment.ended_at is None,
                    }
                    for enrollment in enrollments
                ],
                "guardians": guardians,
                "accountAccess": account_access,
                "canInviteStudentAccount": can_invite_student_account,
                "canRevokeStudentAccount": can_revoke_student_account,
                "canChangeStudent": has_admin_permission(
                    request.user, "academy.change_student"
                ),
                "canAddEnrollment": has_admin_permission(
                    request.user, "academy.add_enrollment"
                ),
                "canFinishEnrollment": has_admin_permission(
                    request.user, "academy.change_enrollment"
                ),
                "availableDisciplines": list(
                    Discipline.objects.filter(is_active=True)
                    .order_by("name")
                    .values("id", "name")
                )
                if has_admin_permission(request.user, "academy.add_enrollment")
                else [],
            }
        )

    def patch(self, request, student_id):
        self.require_permissions("academy.change_student")
        student = get_object_or_404(Student, pk=student_id)
        serializer = StudentInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(student, field, value)
        try:
            with transaction.atomic():
                student.full_clean()
                student.save(
                    update_fields=(*serializer.validated_data.keys(), "updated_at")
                )
                _log_student(
                    request,
                    student,
                    CHANGE,
                    "Datos del alumno actualizados desde el panel.",
                )
        except DjangoValidationError as error:
            raise ValidationError(_validation_errors(error)) from error
        return Response({"id": student.pk})


class AdminStudentInvitationCreateView(AdminAcademicAPIView):
    def post(self, request, student_id):
        self.require_permissions("academy.invite_student_account")
        serializer = StudentInvitationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = get_object_or_404(Student, pk=student_id)
        try:
            invitation, token = issue_student_invitation(
                student_id=student.pk,
                email=serializer.validated_data["email"],
                created_by=request.user,
            )
        except InvitationAlreadyPending as error:
            raise ValidationError(
                {
                    "invitation": "Ya hay una invitación vigente para este alumno "
                    "o este correo."
                }
            ) from error
        except DjangoValidationError as error:
            raise ValidationError(_validation_errors(error)) from error
        except IntegrityError as error:
            raise ValidationError(
                {
                    "invitation": "Ya hay una invitación vigente para este alumno "
                    "o este correo."
                }
            ) from error

        if not send_student_invitation_email(invitation, token):
            revoke_student_invitation(
                invitation_id=invitation.pk,
                student_id=student.pk,
                actor=request.user,
            )
            return Response(
                {
                    "detail": "No pudimos enviar la invitación. "
                    "Podés intentarlo de nuevo."
                },
                status=503,
            )

        _log_invitation(request, invitation, ADDITION, "Invitación académica enviada.")
        return Response(
            {"detail": "Invitación enviada al correo indicado."}, status=201
        )


class AdminStudentInvitationCancelView(AdminAcademicAPIView):
    def post(self, request, student_id, invitation_id):
        self.require_permissions("academy.invite_student_account")
        get_object_or_404(Student, pk=student_id)
        try:
            invitation = revoke_student_invitation(
                invitation_id=invitation_id,
                student_id=student_id,
                actor=request.user,
            )
        except AccountInvitation.DoesNotExist as error:
            raise Http404 from error
        except DjangoValidationError as error:
            raise ValidationError(_validation_errors(error)) from error
        _log_invitation(request, invitation, CHANGE, "Invitación académica cancelada.")
        return Response({"detail": "La invitación fue cancelada."})


class AdminStudentAccountRevokeView(AdminAcademicAPIView):
    def post(self, request, student_id):
        self.require_permissions("academy.revoke_student_account")
        try:
            with transaction.atomic():
                student = revoke_student_account_link(student_id=student_id)
                _log_student(
                    request,
                    student,
                    CHANGE,
                    "Acceso del alumno revocado desde el panel.",
                )
        except Student.DoesNotExist as error:
            raise Http404 from error
        except DjangoValidationError as error:
            raise ValidationError(_validation_errors(error)) from error
        return Response({"detail": "Se revocó el acceso a la plataforma."})

class AdminStudentEnrollmentCreateView(AdminAcademicAPIView):
    def post(self, request, student_id):
        self.require_permissions("academy.add_enrollment")
        serializer = EnrollmentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = get_object_or_404(Student, pk=student_id)
        discipline = get_object_or_404(
            Discipline, pk=serializer.validated_data["discipline_id"], is_active=True
        )
        try:
            with transaction.atomic():
                enrollment, charge_generation = create_enrollment(
                    student_id=student.pk,
                    discipline_id=discipline.pk,
                    enrolled_at=serializer.validated_data["enrolled_at"],
                    actor=request.user,
                )
                _log_enrollment(
                    request, enrollment, ADDITION, "Inscripción creada desde el panel."
                )
        except DjangoValidationError as error:
            raise ValidationError(_validation_errors(error)) from error
        charge_status = "not_applicable"
        if charge_generation:
            if charge_generation.created:
                charge_status = "created"
            elif charge_generation.missing_prices:
                charge_status = "missing_price"
            else:
                charge_status = "already_exists"
        return Response(
            {"id": enrollment.pk, "initialChargeStatus": charge_status},
            status=201,
        )


class AdminEnrollmentFinishView(AdminAcademicAPIView):
    def post(self, request, student_id, enrollment_id):
        self.require_permissions("academy.change_enrollment")
        enrollment = get_object_or_404(
            Enrollment, pk=enrollment_id, student_id=student_id
        )
        try:
            with transaction.atomic():
                enrollment = finish_enrollment(enrollment_id=enrollment.pk)
                _log_enrollment(
                    request,
                    enrollment,
                    CHANGE,
                    "Inscripción finalizada desde el panel.",
                )
        except DjangoValidationError as error:
            raise ValidationError(_validation_errors(error)) from error
        return Response({"id": enrollment.pk, "endedAt": enrollment.ended_at})


def _validation_errors(error: DjangoValidationError) -> dict:
    if hasattr(error, "message_dict"):
        return error.message_dict
    return {"nonFieldErrors": error.messages}


def _log_student(request, student, action_flag, change_message):
    LogEntry.objects.log_action(
        user_id=request.user.pk,
        content_type_id=ContentType.objects.get_for_model(Student).pk,
        object_id=student.pk,
        object_repr=str(student)[:200],
        action_flag=action_flag,
        change_message=change_message,
    )


def _log_enrollment(request, enrollment, action_flag, change_message):
    LogEntry.objects.log_action(
        user_id=request.user.pk,
        content_type_id=ContentType.objects.get_for_model(Enrollment).pk,
        object_id=enrollment.pk,
        object_repr=str(enrollment)[:200],
        action_flag=action_flag,
        change_message=change_message,
    )


def _log_invitation(request, invitation, action_flag, change_message):
    LogEntry.objects.log_action(
        user_id=request.user.pk,
        content_type_id=ContentType.objects.get_for_model(AccountInvitation).pk,
        object_id=str(invitation.pk),
        object_repr=str(invitation),
        action_flag=action_flag,
        change_message=change_message,
    )
