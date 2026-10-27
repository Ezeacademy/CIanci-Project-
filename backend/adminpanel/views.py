from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import can_access_admin_panel
from .queries import get_admin_dashboard_data


class CanAccessAdminPanel(BasePermission):
    def has_permission(self, request, view):
        return can_access_admin_panel(request.user)


class AdminDashboardView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, CanAccessAdminPanel]

    def get(self, request):
        response = Response(get_admin_dashboard_data(request.user))
        response["Cache-Control"] = "no-store"
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
