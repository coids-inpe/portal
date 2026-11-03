from unittest.mock import Mock, patch

from django.contrib import admin
from django.test import RequestFactory

from apps.infra.admin import HostnameIPAdmin, RedeAdmin
from apps.infra.models import HostnameIP, Rede
from apps.infra.utils import netbox


def test_ipam_queries_netbox_endpoints():
    response = Mock()
    response.json.return_value = {"results": [], "next": None}
    with patch.object(netbox, "NETBOX_URL", "https://netbox.example"), \
         patch.object(netbox.requests, "get", return_value=response) as get:
        assert netbox.get_ip_addresses() == []
        assert netbox.get_prefixes() == []
    assert [call.args[0] for call in get.call_args_list] == [
        "https://netbox.example/api/ipam/ip-addresses/",
        "https://netbox.example/api/ipam/prefixes/",
    ]


def test_hostname_admin_shows_netbox_ip_addresses():
    request = RequestFactory().get("/admin/infra/hostnameip/", {"q": "srv"})
    request.user = Mock(is_authenticated=True, is_staff=True)
    request.user.has_perm.return_value = True
    records = [{"address": "192.0.2.10/24", "dns_name": "srv.example", "status": {"label": "Active"}},
               {"address": "192.0.2.11/24", "dns_name": "other.example"}]
    with patch("apps.infra.admin.get_ip_addresses", return_value=records):
        response = HostnameIPAdmin(HostnameIP, admin.site).changelist_view(request)
    response.render()
    assert b"srv.example" in response.content
    assert b"other.example" not in response.content
    assert b"192.0.2.10/24" in response.content


def test_rede_admin_shows_netbox_prefixes():
    request = RequestFactory().get("/admin/infra/rede/")
    request.user = Mock(is_authenticated=True, is_staff=True)
    request.user.has_perm.return_value = True
    records = [{"prefix": "192.0.2.0/24", "description": "Rede de testes", "status": {"label": "Active"}}]
    with patch("apps.infra.admin.get_prefixes", return_value=records):
        response = RedeAdmin(Rede, admin.site).changelist_view(request)
    response.render()
    assert b"192.0.2.0/24" in response.content
    assert b"Rede de testes" in response.content


def test_ipam_unavailable_shows_error():
    request = RequestFactory().get("/admin/infra/rede/")
    request.user = Mock(is_authenticated=True, is_staff=True)
    request.user.has_perm.return_value = True
    with patch("apps.infra.admin.get_prefixes", return_value=None):
        response = RedeAdmin(Rede, admin.site).changelist_view(request)
    response.render()
    assert response.status_code == 502
    assert "Não foi possível consultar os dados".encode() in response.content
