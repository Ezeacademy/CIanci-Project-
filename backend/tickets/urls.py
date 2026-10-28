from django.urls import path

from .api import (
    AdminSeatMapDetailView,
    AdminShowDetailView,
    AdminShowsView,
    AdminVenueDetailView,
    AdminVenueMapView,
    AdminVenuesView,
)

urlpatterns = [
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
