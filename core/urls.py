from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .views import list_units

urlpatterns = [
    path("", views.home_view, name="home_view"),
    path("healthz/", views.healthcheck_view, name="healthcheck"),
    path("account/", views.account_view, name="account"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="home_view"),
        name="logout",
    ),
    path("expand_inventory/", views.expand_inventory_view, name="expand_inventory"),
    path("create_storage/", views.create_storage_view, name="create_storage"),
    path("add_items_to_unit/", views.add_items_to_unit_view, name="add_items_to_unit"),
    path("units/", list_units, name="list_units"),
    path(
        "user/<int:user_id>/units/<slug:access_token>/",
        views.unit_detail,
        name="unit_detail",
    ),
    path(
        "user/<int:user_id>/units/<slug:access_token>/qr/",
        views.unit_qr_view,
        name="unit_qr",
    ),
    path(
        "user/<int:user_id>/units/<slug:access_token>/edit/",
        views.unit_edit_view,
        name="unit_edit",
    ),
    path(
        "user/<int:user_id>/units/<slug:access_token>/delete/",
        views.unit_delete_view,
        name="unit_delete",
    ),
    path("item/<int:item_id>/", views.item_detail, name="item_detail"),
    path("item/<int:item_id>/edit/", views.item_edit_view, name="item_edit"),
    path("item/<int:item_id>/delete/", views.item_delete_view, name="item_delete"),
    path("find-item/", views.item_search_view, name="item_search"),
    path("api/extract-item-features/", views.extract_item_features_api, name="extract_item_features_api"),
    path("caddy-ca/download/", views.caddy_ca_download_view, name="caddy_ca_download"),
]
