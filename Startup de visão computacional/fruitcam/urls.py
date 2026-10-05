from django.urls import path, re_path
from django.views.generic import RedirectView

from core import line_views, views

urlpatterns = [
    path("api/auth/csrf", views.csrf),
    path("api/auth/login", views.login_view),
    path("api/auth/logout", views.logout_view),
    path("api/auth/me", views.me),
    path("api/analyze", views.analyze),
    path("api/sectors", views.sectors),
    path("api/stats/<str:name>", views.stats_view),
    path("api/cameras", line_views.camera_list),
    path("api/cameras/<slug:slug>/frame", line_views.camera_frame),
    path("api/line", line_views.line_summary),
    re_path(r"^api/", views.api_not_found),
    path("favicon.ico", RedirectView.as_view(url="/static/brand/favicon.ico", permanent=True)),
    re_path(r"^(?!static/).*$", views.spa),
]

handler404 = "core.views.not_found"
handler500 = "core.views.server_error"
