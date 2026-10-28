ADMIN_PANEL_VIEW_PERMISSIONS = (
    "academy.view_student",
    "billing.view_monthlycharge",
    "payments.view_paymentintent",
    "academy.view_classschedule",
)

INSTITUTE_ADMIN_PERMISSIONS = (
    "accounts.view_guardianrelationship",
    "academy.view_student",
    "academy.add_student",
    "academy.change_student",
    "academy.invite_student_account",
    "academy.revoke_student_account",
    "academy.view_enrollment",
    "academy.add_enrollment",
    "academy.change_enrollment",
    "academy.view_discipline",
    "academy.add_discipline",
    "academy.change_discipline",
    "academy.view_teacher",
    "academy.add_teacher",
    "academy.change_teacher",
    "academy.view_classschedule",
    "academy.add_classschedule",
    "academy.change_classschedule",
    "tickets.view_show",
    "tickets.manage_ticketing",
    "billing.view_disciplineprice",
    "billing.view_monthlycharge",
    "billing.add_monthlycharge",
    "billing.view_chargeadjustment",
    "billing.adjust_monthlycharge",
    "payments.view_payment",
    "payments.add_payment",
    "payments.view_paymentintent",
    "payments.change_paymentintent",
    "payments.view_creditrelease",
)


def can_access_admin_panel(user) -> bool:
    """Require staff entry plus explicit read permissions for all dashboard data."""
    return bool(
        user.is_authenticated
        and user.is_active
        and user.is_staff
        and user.has_perms(ADMIN_PANEL_VIEW_PERMISSIONS)
    )


def has_admin_permission(user, permission: str) -> bool:
    """Check both Django Admin entry and the model permission for a real link."""
    return bool(user.is_authenticated and user.is_staff and user.has_perm(permission))


