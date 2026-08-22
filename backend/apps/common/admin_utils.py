"""Reusable Django admin helpers for the project.

Every business model should remain inspectable from Django Admin as a
super-admin/debug fallback, even though the React dashboard is the primary
operations UI.
"""
from __future__ import annotations

from django.apps import apps
from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered
from django.db import models


def _build_list_display(model: type[models.Model]) -> tuple[str, ...]:
    """Create a compact, safe list display without including M2M/Text/JSON fields."""
    fields: list[str] = []
    preferred = (
        "id",
        "uuid",
        "name",
        "full_name",
        "title",
        "product",
        "variant",
        "sku",
        "phone",
        "email",
        "order_number",
        "purchase_number",
        "code",
        "status",
        "is_active",
        "active",
        "created_at",
        "updated_at",
    )
    concrete = {field.name: field for field in model._meta.concrete_fields}

    for name in preferred:
        if name in concrete and name not in fields:
            fields.append(name)
        if len(fields) >= 8:
            break

    if not fields:
        fields.append(model._meta.pk.name)

    # Add a few useful scalar fields when preferred names are not enough.
    if len(fields) < 5:
        for field in model._meta.concrete_fields:
            if field.name in fields:
                continue
            if isinstance(field, (models.TextField, models.JSONField, models.BinaryField)):
                continue
            fields.append(field.name)
            if len(fields) >= 5:
                break

    return tuple(fields)


def _build_search_fields(model: type[models.Model]) -> tuple[str, ...]:
    searchable: list[str] = []
    preferred = (
        "name",
        "full_name",
        "title",
        "sku",
        "barcode",
        "slug",
        "phone",
        "email",
        "order_number",
        "purchase_number",
        "transaction_id",
        "tracking_number",
        "code",
    )
    concrete = {field.name: field for field in model._meta.concrete_fields}
    for name in preferred:
        field = concrete.get(name)
        if field and isinstance(field, (models.CharField, models.TextField)):
            searchable.append(name)
        if len(searchable) >= 6:
            break
    return tuple(searchable)


def _build_list_filter(model: type[models.Model]) -> tuple[str, ...]:
    filters: list[str] = []
    for field in model._meta.concrete_fields:
        if isinstance(field, models.BooleanField) or getattr(field, "choices", None):
            filters.append(field.name)
        if len(filters) >= 5:
            break
    return tuple(filters)


def _build_autocomplete_or_raw_fields(model: type[models.Model]) -> tuple[str, ...]:
    """Use raw-id widgets for FK fields to keep large admin forms responsive."""
    fields: list[str] = []
    for field in model._meta.concrete_fields:
        if isinstance(field, (models.ForeignKey, models.OneToOneField)):
            fields.append(field.name)
    return tuple(fields)


def register_app_models(app_label: str, *, exclude: set[type[models.Model]] | None = None) -> None:
    """Register all concrete models from one local Django app.

    This deliberately avoids GenericForeignKey magic and only works with real
    Django models returned by the app registry.
    """
    excluded = exclude or set()
    app_config = apps.get_app_config(app_label)

    for model in app_config.get_models():
        if model in excluded or model._meta.abstract:
            continue

        attrs = {
            "list_display": _build_list_display(model),
            "search_fields": _build_search_fields(model),
            "list_filter": _build_list_filter(model),
            "raw_id_fields": _build_autocomplete_or_raw_fields(model),
            "list_per_page": 50,
            "show_full_result_count": False,
        }
        admin_class = type(f"{model.__name__}Admin", (admin.ModelAdmin,), attrs)

        try:
            admin.site.register(model, admin_class)
        except AlreadyRegistered:
            # Explicit custom admins are allowed to win.
            pass
