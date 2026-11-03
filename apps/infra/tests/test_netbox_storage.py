import json
from unittest.mock import Mock, patch

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import RequestFactory
from django.urls import reverse
import pytest

from apps.infra.admin import StorageAdmin
from apps.infra.models import Storage
from apps.infra.utils import netbox


def test_storage_sidebar_label():
    assert Storage._meta.verbose_name_plural == "Storages | controllers"


def test_storage_inventory_keeps_only_requested_netbox_roles():
    from apps.infra.services.netbox_storage import get_storage_inventory

    devices = [
        {"id": 1, "name": "C1", "role": {"slug": "controller", "name": "Controller"}},
        {"id": 2, "name": "D1", "role": {"slug": "disk-array", "name": "Disk Array"}},
        {"id": 3, "name": "S1", "role": {"slug": "storage", "name": "Storage"}},
        {"id": 4, "name": "WEB", "role": {"slug": "server", "name": "Server"}},
    ]
    with patch("apps.infra.services.netbox_storage.get_storage_devices", return_value=devices):
        result = get_storage_inventory()
    assert [item["name"] for item in result] == ["C1", "D1", "S1"]


def test_storage_query_resolves_custom_role_slugs():
    roles_response = Mock()
    roles_response.json.return_value = {"results": [
        {"id": 5, "name": "Controller", "slug": "ctrl-custom"},
        {"id": 6, "name": "Disk Array", "slug": "disk-custom"},
        {"id": 7, "name": "Storage", "slug": "storage-custom"},
    ], "next": None}
    devices_response = Mock()
    devices_response.json.return_value = {"results": [{"id": 1}], "next": None}
    with patch.object(netbox, "NETBOX_URL", "https://netbox.example"), \
         patch.object(netbox.requests, "get", side_effect=[roles_response, devices_response]) as get:
        assert netbox.get_storage_devices() == [{"id": 1}]
    assert "role_id=5" in get.call_args.args[0]
    assert "role_id=6" in get.call_args.args[0]
    assert "role_id=7" in get.call_args.args[0]


def test_storage_admin_changelist_uses_netbox_inventory():
    request = RequestFactory().get("/admin/infra/storage/")
    request.user = Mock(is_authenticated=True, is_staff=True)
    request.user.has_module_perms.return_value = True
    request.user.has_perm.return_value = True
    model_admin = StorageAdmin(Storage, admin.site)
    with patch("apps.infra.admin.get_storage_inventory", return_value=[{"id": 1, "name": "Storage 1", "role": "Storage", "rack": "R1", "site": "CPT", "status": "Ativo", "model": "M1"}]):
        response = model_admin.changelist_view(request)
    response.render()
    assert response.status_code == 200
    assert b"Storage 1" in response.content
    assert b"netbox-storage-card" in response.content
    assert b"infra/css/netbox_storage.css" in response.content
    assert b"netbox-storage-dialog" in response.content
    assert b"infra/js/netbox_storage.js" in response.content


def test_storage_admin_requires_model_permission():
    request = RequestFactory().get("/admin/infra/storage/")
    request.user = Mock(is_authenticated=True, is_staff=True)
    request.user.has_perm.return_value = False
    model_admin = StorageAdmin(Storage, admin.site)
    with pytest.raises(PermissionDenied):
        model_admin.changelist_view(request)


def test_storage_admin_filters_role_and_searches_name():
    request = RequestFactory().get("/admin/infra/storage/", {"role": "storage", "q": "dados"})
    request.user = Mock(is_authenticated=True, is_staff=True)
    request.user.has_perm.return_value = True
    inventory = [
        {"id": 1, "name": "Array Dados", "role": "Disk Array", "role_key": "disk-array", "rack": "R1", "site": "CPT", "status": "Ativo", "model": "M1"},
        {"id": 2, "name": "Array Backup", "role": "Disk Array", "role_key": "disk-array", "rack": "R1", "site": "CPT", "status": "Ativo", "model": "M2"},
        {"id": 3, "name": "Storage Dados", "role": "Storage", "role_key": "storage", "rack": "R1", "site": "CPT", "status": "Ativo", "model": "M3"},
    ]
    with patch("apps.infra.admin.get_storage_inventory", return_value=inventory):
        response = StorageAdmin(Storage, admin.site).changelist_view(request)
    response.render()
    assert b"Array Dados" in response.content
    assert b"Array Backup" not in response.content
    assert b"Storage Dados" in response.content
    assert b'value="storage" selected' in response.content
    assert b'<option value="disk-array"' not in response.content


def test_storage_card_opens_netbox_details():
    from apps.infra.services.netbox_storage import get_storage_detail

    device = {"id": 9, "name": "Storage A", "role": {"name": "Storage"},
              "device_type": {"model": "PowerStore", "manufacturer": {"name": "Dell"}},
              "serial": "SN123", "rack": {"name": "R01"}, "site": {"name": "CPT"}}
    with patch("apps.infra.services.netbox_storage.get_device_data", return_value=device):
        assert get_storage_detail(9)["serial"] == "SN123"

    request = RequestFactory().get(reverse("admin:infra_storage_netbox_detail", args=[9]))
    request.user = Mock(is_authenticated=True, is_staff=True)
    request.user.has_perm.return_value = True
    with patch("apps.infra.admin.get_storage_detail", return_value={"name": "Storage A", "serial": "SN123"}):
        response = StorageAdmin(Storage, admin.site).netbox_detail_view(request, device_id=9)
    assert response.status_code == 200
    assert json.loads(response.content)["device"]["serial"] == "SN123"


def test_storage_detail_rejects_other_device_roles():
    from apps.infra.services.netbox_storage import get_storage_detail

    with patch("apps.infra.services.netbox_storage.get_device_data", return_value={"id": 9, "role": {"name": "Server"}}):
        assert get_storage_detail(9) == {}
    request = RequestFactory().get("/admin/infra/storage/netbox/9/")
    request.user = Mock(is_authenticated=True, is_staff=True)
    request.user.has_perm.return_value = True
    with patch("apps.infra.admin.get_storage_detail", return_value={}):
        with pytest.raises(Http404):
            StorageAdmin(Storage, admin.site).netbox_detail_view(request, device_id=9)
