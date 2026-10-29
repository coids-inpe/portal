import json
from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser
from django.apps import apps
from django.test import RequestFactory
from django.urls import reverse

from apps.infra.views import GetNetboxRacksView
from apps.infra.services.rack_visualization import RackVisualizationService
from apps.infra.utils import netbox


def test_rack_inventory_is_owned_by_netbox():
    assert all(model.__name__ != "Rack" for model in apps.get_app_config("infra").get_models())


def test_datacenter_renders_its_own_page():
    from apps.infra.views import DataCenterView
    request = RequestFactory().get(reverse("infra:datacenter"))
    request.user = type("User", (), {"is_authenticated": True})()
    response = DataCenterView.as_view()(request)
    response.render()
    assert response.status_code == 200
    assert b"Data Center" in response.content


def test_netbox_racks_fetches_all_pages():
    first = Mock()
    first.json.return_value = {"results": [{"id": 1}], "next": "https://netbox.example/api/dcim/racks/?offset=1"}
    second = Mock()
    second.json.return_value = {"results": [{"id": 2}], "next": None}

    with patch.object(netbox, "NETBOX_URL", "https://netbox.example"), \
         patch.object(netbox.requests, "get", side_effect=[first, second]) as get:
        assert netbox.get_rack_data() == [{"id": 1}, {"id": 2}]

    assert get.call_count == 2


def test_netbox_v2_token_uses_bearer_authentication():
    response = Mock()
    response.json.return_value = {"results": [], "next": None}

    with patch.object(netbox, "NETBOX_URL", "https://netbox.example"), \
         patch.object(netbox, "NETBOX_TOKEN", "nbt_key.secret"), \
         patch.object(netbox.requests, "get", return_value=response) as get:
        netbox.get_rack_data()

    assert get.call_args.kwargs["headers"]["Authorization"] == "Bearer nbt_key.secret"


def test_netbox_racks_requires_login():
    request = RequestFactory().get(reverse("infra:netbox_racks"))
    request.user = AnonymousUser()

    response = GetNetboxRacksView.as_view()(request)

    assert response.status_code == 302


def test_netbox_racks_shows_front_occupancy_only():
    request = RequestFactory().get(reverse("infra:netbox_racks"))
    request.user = Mock(is_authenticated=True)
    request.user.has_perm.return_value = True
    rack = {"id": 7, "name": "R01", "u_height": 42, "device_count": 2,
            "site": {"name": "CPT"}, "location": {"name": "Sala 1"},
            "status": {"label": "Ativo"}}
    front = [{"id": 1, "occupied": True}, {"id": 2, "occupied": True}]

    with patch("apps.infra.services.rack_visualization.get_rack_data", return_value=[rack]), \
         patch("apps.infra.services.rack_visualization.get_rack_elevation", return_value=front) as elevation:
        response = GetNetboxRacksView.as_view()(request)

    response.render()
    assert response.context_data["racks"][0]["occupied_units"] == 2
    assert response.context_data["racks"][0]["occupancy_percent"] == 5
    slots = response.context_data["racks"][0]["slots"]
    assert slots[0]["number"] == 42
    assert slots[-1] == {"number": 1, "front": "full"}
    assert slots[-2] == {"number": 2, "front": "full"}
    elevation.assert_called_once_with(7, "front")
    assert b"R01" in response.content
    assert b'aria-label="Rack R01' in response.content
    assert b"Traseira" not in response.content
    assert b"<table" not in response.content


def test_visualization_service_builds_occupancy_without_a_request():
    rack = {"id": 7, "name": "R01", "u_height": 2}
    front = [
        {"id": 1, "occupied": True},
        {"id": 1.5, "occupied": True},
        {"id": 2, "occupied": True},
    ]

    with patch(
        "apps.infra.services.rack_visualization.get_rack_elevation",
        return_value=front,
    ):
        card = RackVisualizationService().build_card(rack)

    assert card["occupied_units"] == 2
    assert card["occupancy_percent"] == 100
    assert card["slots"] == [
        {"number": 2, "front": "full"},
        {"number": 1, "front": "full"},
    ]


def test_netbox_racks_loads_twelve_at_a_time():
    racks = [{"id": i, "name": f"R{i}", "u_height": 2} for i in range(1, 26)]
    request = RequestFactory().get(reverse("infra:netbox_racks"))
    request.user = Mock(is_authenticated=True)
    request.user.has_perm.return_value = True

    with patch("apps.infra.services.rack_visualization.get_rack_data", return_value=racks), \
         patch("apps.infra.services.rack_visualization.get_rack_elevation", return_value=[]) as elevation:
        first = GetNetboxRacksView.as_view()(request)
        first.render()
        assert len(first.context_data["racks"]) == 12
        assert first.context_data["next_offset"] == 12
        assert elevation.call_count == 12

        request = RequestFactory().get(reverse("infra:netbox_racks"), {"partial": "1", "offset": "12"})
        request.user = Mock(is_authenticated=True)
        request.user.has_perm.return_value = True
        second = GetNetboxRacksView.as_view()(request)
        assert second.status_code == 200
        payload = json.loads(second.content)
        assert payload["next_offset"] == 24
        assert "R13" in payload["html"]
        assert "R12" not in payload["html"]
        assert elevation.call_count == 24


def test_netbox_racks_filters_name_and_group_across_batches():
    racks = [
        {"id": i, "name": f"Rack-{i}", "u_height": 2,
         "group": {"id": 1 if i <= 20 else 2, "name": "Grupo A" if i <= 20 else "Grupo B"}}
        for i in range(1, 27)
    ]
    url = reverse("infra:netbox_racks")

    with patch("apps.infra.services.rack_visualization.get_rack_data", return_value=racks), \
         patch("apps.infra.services.rack_visualization.get_rack_elevation", return_value=[]) as elevation:
        request = RequestFactory().get(url, {"q": "rack-", "group": "1"})
        request.user = Mock(is_authenticated=True)
        request.user.has_perm.return_value = True
        first = GetNetboxRacksView.as_view()(request)
        first.render()
        assert first.context_data["total_racks"] == 20
        assert first.context_data["next_offset"] == 12
        assert len(first.context_data["groups"]) == 2
        assert b'value="1" selected' in first.content
        assert elevation.call_count == 12

        request = RequestFactory().get(url, {"q": "rack-", "group": "1", "offset": "12", "partial": "1"})
        request.user = Mock(is_authenticated=True)
        request.user.has_perm.return_value = True
        second = GetNetboxRacksView.as_view()(request)
        payload = json.loads(second.content)
        assert payload["next_offset"] is None
        assert payload["html"].count('class="netbox-rack"') == 8
        assert "Rack-21" not in payload["html"]
        assert elevation.call_count == 20


def test_netbox_racks_shows_api_error():
    request = RequestFactory().get(reverse("infra:netbox_racks"), HTTP_REFERER="/infra/datacenter/")
    request.user = Mock(is_authenticated=True)
    request.user.has_perm.return_value = True

    with patch("apps.infra.services.rack_visualization.get_rack_data", return_value=None):
        response = GetNetboxRacksView.as_view()(request)

    assert response.status_code == 503
    assert b"NetBox indispon\xc3\xadvel" in response.content
    assert b'href="/infra/datacenter/"' in response.content


def test_netbox_error_ignores_external_return_url():
    request = RequestFactory().get(reverse("infra:netbox_racks"), HTTP_REFERER="https://other.example/path")
    request.user = Mock(is_authenticated=True)
    with patch("apps.infra.services.rack_visualization.get_rack_data", return_value=None):
        response = GetNetboxRacksView.as_view()(request)
    assert response.status_code == 503
    assert b'href="/infra/datacenter/"' in response.content


def test_vm_creation_shows_service_error_when_xen_is_down():
    from apps.infra.views import CriarVmView

    request = RequestFactory().post(reverse("infra:netbox_racks"), HTTP_REFERER="/infra/datacenter/")
    request.user = Mock(is_authenticated=True)
    view = CriarVmView()
    view.request = request
    template = Mock()
    form = Mock(cleaned_data={"servidor": 1, "template": template, "memoria": 1, "cpu": 1})
    with patch("apps.infra.views.get_object_or_404", return_value=Mock()), \
         patch("apps.infra.views.XenCrud", side_effect=OSError("offline")):
        response = view.form_valid(form)
    assert response.status_code == 503
    assert b"Xen indispon" in response.content


def test_netbox_elevation_failure_shows_service_error():
    request = RequestFactory().get(reverse("infra:netbox_racks"))
    request.user = Mock(is_authenticated=True)
    with patch("apps.infra.services.rack_visualization.get_rack_data", return_value=[{"id": 1, "name": "R1", "u_height": 2}]), \
         patch("apps.infra.services.rack_visualization.get_rack_elevation", return_value=None):
        response = GetNetboxRacksView.as_view()(request)
    assert response.status_code == 503


def test_freeipa_failure_shows_service_error():
    from python_freeipa.exceptions import FreeIPAError
    from apps.infra.views import CriarServidorLdapView

    request = RequestFactory().get("/infra/servidor/1/criarservidorldap/", HTTP_REFERER="/admin/infra/servidor/1/change/")
    request.user = Mock(is_authenticated=True)
    request.user.has_perms.return_value = True
    server = Mock(conta="Aguardando")
    server.grupos_acesso.all.return_value.exists.return_value = True
    with patch("apps.infra.views.get_object_or_404", return_value=server), \
         patch("apps.infra.views.FreeIPA", side_effect=FreeIPAError("offline")):
        response = CriarServidorLdapView.as_view()(request, pk=1)
    assert response.status_code == 503
    assert b"FreeIPA indispon" in response.content
