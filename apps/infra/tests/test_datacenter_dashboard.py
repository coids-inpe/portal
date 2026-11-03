from unittest.mock import Mock, patch

from django.test import RequestFactory
from django.urls import reverse

from apps.infra.views import DataCenterView
from apps.infra.utils import netbox


def test_sites_fetches_every_netbox_page():
    first = Mock()
    first.json.return_value = {"results": [{"id": 1}], "next": "https://netbox.example/next"}
    second = Mock()
    second.json.return_value = {"results": [{"id": 2}], "next": None}
    with patch.object(netbox, "NETBOX_URL", "https://netbox.example"), \
         patch.object(netbox.requests, "get", side_effect=[first, second]):
        assert netbox.get_sites() == [{"id": 1}, {"id": 2}]


def test_dashboard_shows_totals_and_servers():
    request = RequestFactory().get(reverse("infra:datacenter"))
    request.user = Mock(is_authenticated=True)
    racks = [{"id": 10, "name": "R01", "u_height": 4, "device_count": 2,
              "site": {"id": 1, "name": "CPT"}, "status": {"value": "active"}}]
    with patch("apps.infra.services.datacenter_dashboard.get_rack_data", return_value=racks), \
         patch("apps.infra.services.datacenter_dashboard.get_server_devices", return_value={"count": 8, "results": [], "next": None}) as servers, \
         patch("apps.infra.services.datacenter_dashboard.get_sites", return_value=[{"id": 1, "name": "CPT", "status": {"value": "active"}, "description": "Sala principal"}]), \
         patch("apps.infra.services.datacenter_dashboard.get_storage_inventory", return_value=[
             {"id": 2, "role_key": "storage"},
             {"id": 3, "role_key": "controller"},
             {"id": 4, "role_key": "disk-array"},
         ]), \
         patch("apps.infra.services.datacenter_dashboard.get_ip_addresses", return_value=[{"id": 3}]), \
         patch("apps.infra.services.datacenter_dashboard.get_prefixes", return_value=[{"id": 4}]), \
         patch("apps.infra.services.datacenter_dashboard.get_rack_elevation", return_value=[{"id": 1, "occupied": True}]):
        response = DataCenterView.as_view()(request)
    response.render()
    assert response.context_data["totals"] == {"racks": 1, "devices": 2, "servers": 8, "storages": 2, "ips": 1, "networks": 1}
    servers.assert_called_once_with(limit=1)
    assert b"Servidores" in response.content
    assert b'datacenter-sites' in response.content
    assert b"Sala principal" in response.content
    assert response.content.count(b">Sites</span>") == 0
    assert b"R01" in response.content


def test_dashboard_survives_unavailable_netbox_sections():
    request = RequestFactory().get(reverse("infra:datacenter"))
    request.user = Mock(is_authenticated=True)
    with patch("apps.infra.services.datacenter_dashboard.get_rack_data", return_value=None), \
         patch("apps.infra.services.datacenter_dashboard.get_server_devices", return_value=None), \
         patch("apps.infra.services.datacenter_dashboard.get_sites", return_value=None), \
         patch("apps.infra.services.datacenter_dashboard.get_storage_inventory", return_value=None), \
         patch("apps.infra.services.datacenter_dashboard.get_ip_addresses", return_value=None), \
         patch("apps.infra.services.datacenter_dashboard.get_prefixes", return_value=None):
        response = DataCenterView.as_view()(request)
    response.render()
    assert response.status_code == 200
    assert response.context_data["totals"]["racks"] is None
    assert "indisponíveis".encode() in response.content
