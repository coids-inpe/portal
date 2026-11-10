from unittest.mock import Mock, patch
import json

import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse

from apps.infra.admin import ServidorAdmin
from apps.infra.models import Servidor
from apps.infra.services.netbox_server import get_server_inventory, get_server_detail
from apps.infra.utils import netbox


def test_server_query_uses_server_role():
    roles = Mock()
    roles.json.return_value = {"results": [{"id": 5, "name": "Server"}, {"id": 6, "name": "Storage"}], "next": None}
    devices = Mock()
    devices.json.return_value = {"count": 31, "results": [{"id": 9}], "next": "https://netbox.example/next"}
    with patch.object(netbox, "NETBOX_URL", "https://netbox.example"), \
         patch.object(netbox.requests, "get", side_effect=[roles, devices]) as get:
        assert netbox.get_server_devices(limit=15, offset=15, search="srv") == devices.json.return_value
    assert "role_id=5" in get.call_args.args[0]
    assert "role_id=6" not in get.call_args.args[0]
    assert "limit=15" in get.call_args.args[0]
    assert "offset=15" in get.call_args.args[0]
    assert "name__ic=srv" in get.call_args.args[0]


def test_server_inventory_and_detail():
    device = {"id": 9, "name": "srv01", "role": {"name": "Server"}, "status": {"value": "active"},
              "site": {"name": "CPT"}, "rack": {"name": "R01"},
              "device_type": {"model": "R710", "manufacturer": {"name": "Dell"}},
              "asset_tag": "PAT-123", "face": {"value": "front", "label": "Front"}}
    with patch("apps.infra.services.netbox_server.get_server_devices", return_value={"count": 1, "results": [device], "next": None}), \
         patch("apps.infra.services.netbox_server.get_device_data", return_value=device):
        assert get_server_inventory()["devices"][0]["status"] == "Ativo"
        assert get_server_inventory()["devices"][0]["asset_tag"] == "PAT-123"
        assert get_server_detail(9)["model"] == "R710"
        assert get_server_detail(9)["face"] == "Front"


def test_server_detail_endpoint_returns_device():
    request = RequestFactory().get(reverse("admin:infra_servidor_netbox_detail", args=[9]))
    request.user = Mock(is_authenticated=True, is_staff=True)
    request.user.has_perm.return_value = True
    with patch("apps.infra.admin.get_server_detail", return_value={"name": "srv01"}):
        response = ServidorAdmin(Servidor, admin.site).netbox_detail_view(request, 9)
    assert json.loads(response.content)["device"]["name"] == "srv01"


@pytest.mark.django_db
def test_server_admin_shows_only_netbox_cards():
    request = RequestFactory().get(reverse("admin:infra_servidor_changelist"))
    request.user = Mock(is_authenticated=True, is_staff=True, is_superuser=True)
    request.user.has_perm.return_value = True
    request.user.has_module_perms.return_value = True
    server = {"id": 9, "name": "srv01", "role": "Server", "site": "CPT", "rack": "R01", "model": "R710", "status": "Ativo", "asset_tag": "PAT-123"}
    with patch("apps.infra.admin.get_server_inventory", return_value={"devices": [server], "count": 1, "next_offset": None, "previous_offset": None}):
        response = ServidorAdmin(Servidor, admin.site).changelist_view(request)
    response.render()
    assert b"srv01" in response.content
    assert b"PAT-123" in response.content
    assert b"netbox-storage-card" in response.content
    assert reverse("admin:infra_servidor_netbox_detail", args=[9]).encode() in response.content
    assert b'Ver mais' in response.content
    assert "Associar servidor do NetBox".encode() not in response.content
    assert reverse("admin:infra_servidor_operacionais").encode() not in response.content
    assert b"No record" not in response.content
    assert b"changelist-form" not in response.content


@pytest.mark.django_db
def test_server_admin_requests_only_one_page():
    request = RequestFactory().get(reverse("admin:infra_servidor_changelist"), {"netbox_q": "srv", "netbox_offset": "15"})
    request.user = Mock(is_authenticated=True, is_staff=True, is_superuser=True)
    request.user.has_perm.return_value = True
    request.user.has_module_perms.return_value = True
    page = {"devices": [], "count": 31, "next_offset": 30, "previous_offset": 0}
    with patch("apps.infra.admin.get_server_inventory", return_value=page) as get:
        response = ServidorAdmin(Servidor, admin.site).changelist_view(request)
    response.render()
    get.assert_called_once_with(limit=15, offset=15, search="srv", asset_tag="")
    assert b"netbox_offset=30" in response.content
    assert "Carregar mais".encode() in response.content
