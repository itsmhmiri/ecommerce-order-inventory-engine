"""
Unit test verifying environment setup, settings, and app registry.
"""

import pytest
from django.conf import settings
from django.apps import apps

def test_settings_loaded():
    assert settings.SECRET_KEY is not None
    assert "apps.common.apps.CommonConfig" in settings.INSTALLED_APPS
    assert "apps.catalog.apps.CatalogConfig" in settings.INSTALLED_APPS
    assert "apps.inventory.apps.InventoryConfig" in settings.INSTALLED_APPS
    assert "apps.cart.apps.CartConfig" in settings.INSTALLED_APPS
    assert "apps.orders.apps.OrdersConfig" in settings.INSTALLED_APPS
    assert "apps.payments.apps.PaymentsConfig" in settings.INSTALLED_APPS
    assert "rest_framework" in settings.INSTALLED_APPS
    assert "drf_spectacular" in settings.INSTALLED_APPS

def test_app_registry():
    assert apps.is_installed("apps.common")
    assert apps.is_installed("apps.catalog")
    assert apps.is_installed("apps.inventory")
    assert apps.is_installed("apps.cart")
    assert apps.is_installed("apps.orders")
    assert apps.is_installed("apps.payments")
    assert apps.is_installed("apps.authentication")
