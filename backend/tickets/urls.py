from django.urls import path

from .api import (
    AdminFunctionDetailView,
    AdminSeatMapDetailView,
    AdminShowDetailView,
    AdminShowsView,
    AdminVenueDetailView,
    AdminVenueMapView,
    AdminVenuesView,
    PublicFunctionSeatMapOverviewView,
    PublicFunctionSeatMapView,
    PublicFunctionSeatSectionView,
    PublicShowDetailView,
    PublicShowsView,
)

urlpatterns = [
    path("ticketing/shows", PublicShowsView.as_view(), name="public-ticketing-shows"),
    path(
        "ticketing/shows/<int:show_id>",
        PublicShowDetailView.as_view(),
        name="public-ticketing-show-detail",
    ),
    path(
        "ticketing/shows/<int:show_id>/functions/<int:function_id>/seat-map",
        PublicFunctionSeatMapView.as_view(),
        name="public-ticketing-function-seat-map",
    ),
    path(
        "ticketing/shows/<int:show_id>/functions/<int:function_id>/seat-map/overview",
        PublicFunctionSeatMapOverviewView.as_view(),
        name="public-ticketing-function-seat-map-overview",
    ),
    path(
        "ticketing/shows/<int:show_id>/functions/<int:function_id>/seat-map/sections/<int:section_id>",
        PublicFunctionSeatSectionView.as_view(),
        name="public-ticketing-function-seat-map-section",
    ),
    path(
        "admin/ticketing/shows", AdminShowsView.as_view(), name="admin-ticketing-shows"
    ),
    path(
        "admin/ticketing/shows/<int:show_id>",
        AdminShowDetailView.as_view(),
        name="admin-ticketing-show-detail",
    ),
    path(
        "admin/ticketing/shows/<int:show_id>/functions",
        AdminShowDetailView.as_view(),
        name="admin-ticketing-show-functions",
    ),
    path(
        "admin/ticketing/functions/<int:function_id>",
        AdminFunctionDetailView.as_view(),
        name="admin-ticketing-function-detail",
    ),
    path(
        "admin/ticketing/venues",
        AdminVenuesView.as_view(),
        name="admin-ticketing-venues",
    ),
    path(
        "admin/ticketing/venues/<int:venue_id>",
        AdminVenueDetailView.as_view(),
        name="admin-ticketing-venue-detail",
    ),
    path(
        "admin/ticketing/venues/<int:venue_id>/maps",
        AdminVenueMapView.as_view(),
        name="admin-ticketing-venue-maps",
    ),
    path(
        "admin/ticketing/maps/<int:map_version_id>",
        AdminSeatMapDetailView.as_view(),
        name="admin-ticketing-map-detail",
    ),
]
