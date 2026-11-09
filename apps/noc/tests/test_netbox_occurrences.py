from unittest.mock import Mock, patch

import pytest
import requests
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.urls import reverse
from mixer.backend.django import mixer

from apps.infra.models import Equipamento, Ocorrencia
from apps.noc.forms import NetBoxOcorrenciaForm
from apps.noc.models import Checklist
from apps.noc import netbox

pytestmark = pytest.mark.django_db
DEVICE = {"id": 842, "name": "servidor-01", "site": {"name": "CPT"}, "rack": {"name": "R01"}}


@pytest.fixture(autouse=True)
def netbox_test_config(monkeypatch):
    monkeypatch.setattr(netbox.client, "NETBOX_URL", "https://netbox.example")
    monkeypatch.setattr(netbox.client, "NETBOX_TOKEN", "test-token")


def test_new_occurrence_saves_netbox_reference_without_local_inventory():
    before = Equipamento.objects.count()
    with patch("apps.noc.forms.get_device", return_value=DEVICE) as get:
        form = NetBoxOcorrenciaForm(data={"netbox_device": "842", "descricao": "Falha no disco"})
        assert form.is_valid(), form.errors
        item = form.save()
    get.assert_called_once_with(842)
    item.refresh_from_db()
    assert (item.netbox_object_type, item.netbox_object_id, item.equipamento_nome) == ("dcim.device", 842, "servidor-01")
    assert item.equipamento_id is None
    assert Equipamento.objects.count() == before


def test_invalid_selection_keeps_description_and_reports_error():
    with patch("apps.noc.forms.get_device", side_effect=netbox.NetBoxError("NetBox indisponível.", 503)):
        form = NetBoxOcorrenciaForm(data={"netbox_device": "842", "descricao": "Texto preservado"})
        assert not form.is_valid()
    assert "netbox_device" in form.errors
    assert "Texto preservado" in str(form)


@pytest.mark.parametrize("value", ["", "0", "-1", "https://example.com/842", "abc"])
def test_new_occurrence_requires_a_positive_device_id(value):
    with patch("apps.noc.forms.get_device") as get:
        form = NetBoxOcorrenciaForm(data={"netbox_device": value, "descricao": "Relato"})
        assert not form.is_valid()
    get.assert_not_called()


def test_existing_external_occurrence_keeps_snapshot_without_network():
    item = Ocorrencia.objects.create(netbox_object_type="dcim.device", netbox_object_id=842, equipamento_nome="Nome original", descricao="Antes")
    with patch("apps.noc.forms.get_device") as get:
        form = NetBoxOcorrenciaForm(data={"netbox_device": "842", "descricao": "Depois"}, instance=item)
        assert form.is_valid(), form.errors
        form.save()
    get.assert_not_called()
    item.refresh_from_db()
    assert item.equipamento_nome == "Nome original"
    assert item.descricao == "Depois"


def test_existing_external_occurrence_cannot_lose_its_reference():
    item = Ocorrencia.objects.create(netbox_object_type="dcim.device", netbox_object_id=842, equipamento_nome="Original")
    form = NetBoxOcorrenciaForm(data={"netbox_device": "", "descricao": "Relato"}, instance=item)
    assert not form.is_valid()


def test_legacy_occurrence_can_be_edited_without_netbox():
    item = Ocorrencia.objects.create(equipamento=mixer.blend(Equipamento))
    original_id = item.equipamento_id
    with patch("apps.noc.forms.get_device") as get:
        form = NetBoxOcorrenciaForm(data={"netbox_device": "", "descricao": "Atualizado"}, instance=item)
        assert form.is_valid(), form.errors
        form.save()
    get.assert_not_called()
    assert item.equipamento_id == original_id
    assert item.equipamento_identificacao == str(item.equipamento)


def test_legacy_occurrence_can_be_explicitly_reassociated():
    item = Ocorrencia.objects.create(equipamento=mixer.blend(Equipamento))
    with patch("apps.noc.forms.get_device", return_value=DEVICE):
        form = NetBoxOcorrenciaForm(data={"netbox_device": "842", "descricao": "Relato"}, instance=item)
        assert form.is_valid(), form.errors
        form.save()
    assert item.equipamento_id is None
    assert item.equipamento_identificacao == "servidor-01"


def test_legacy_occurrence_without_equipment_can_still_be_edited():
    item = Ocorrencia.objects.create(descricao="Antigo sem equipamento")
    with patch("apps.noc.forms.get_device") as get:
        form = NetBoxOcorrenciaForm(data={"netbox_device": "", "descricao": "Atualizado"}, instance=item)
        assert form.is_valid(), form.errors
        form.save()
    get.assert_not_called()
    assert item.equipamento_identificacao == "Sem equipamento"


def test_read_only_inline_displays_the_historical_equipment():
    from django.contrib.admin import site
    from django.contrib.admin.helpers import AdminReadonlyField
    from apps.noc.admin import OcorrenciaNetBoxInline

    item = Ocorrencia(netbox_object_type="dcim.device", netbox_object_id=842, equipamento_nome="Nome original")
    form = NetBoxOcorrenciaForm(instance=item)
    field = AdminReadonlyField(form, "netbox_device", False, model_admin=OcorrenciaNetBoxInline(Checklist, site))
    assert "Nome original" in str(field.contents())


@pytest.mark.parametrize("fields", [
    {"netbox_object_type": "dcim.device"},
    {"netbox_object_id": 842},
    {"netbox_object_type": "ipam.prefix", "netbox_object_id": 842, "equipamento_nome": "Rede"},
    {"netbox_object_type": "dcim.device", "netbox_object_id": 842},
])
def test_model_rejects_incomplete_or_unsupported_references(fields):
    with pytest.raises(ValidationError):
        Ocorrencia(**fields).full_clean()


def test_model_rejects_two_inventory_sources():
    device = mixer.blend(Equipamento)
    item = Ocorrencia(equipamento=device, netbox_object_type="dcim.device", netbox_object_id=842, equipamento_nome="Servidor")
    with pytest.raises(ValidationError):
        item.full_clean()


def test_search_endpoint_requires_staff_and_noc_and_occurrence_permissions(client):
    url = reverse("noc:netbox_devices")
    assert client.get(url).status_code == 302
    user = mixer.blend("colaborador.Colaborador", is_active=True, is_staff=True, is_superuser=False)
    client.force_login(user)
    with patch("apps.noc.views.search_devices") as search:
        assert client.get(url).status_code == 403
    search.assert_not_called()


def test_search_endpoint_paginates_and_does_not_expose_upstream_urls(client):
    user = mixer.blend("colaborador.Colaborador", is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    with patch("apps.noc.views.search_devices", return_value={"results": [{"id": 842, "label": "servidor-01 | CPT | R01"}], "more": True}) as search:
        response = client.get(reverse("noc:netbox_devices"), {"q": "servidor", "offset": "20"})
    assert response.status_code == 200
    assert response.json()["more"] is True
    search.assert_called_once_with("servidor", 20)
    assert client.get(reverse("noc:netbox_devices"), {"offset": "-1"}).status_code == 400


def test_service_uses_fixed_endpoint_and_bounded_pagination():
    response = Mock()
    response.json.return_value = {"results": [DEVICE], "next": "https://untrusted.example/", "count": 21}
    with patch.object(netbox.client, "NETBOX_URL", "https://netbox.example"), patch.object(netbox.requests, "get", return_value=response) as get:
        result = netbox.search_devices("servidor", 20)
    assert result["results"][0]["id"] == 842
    assert result["more"] is True
    assert get.call_count == 1
    assert get.call_args.args[0] == "https://netbox.example/api/dcim/devices/"
    assert get.call_args.kwargs["params"] == {"q": "servidor", "limit": 20, "offset": 20}


@pytest.mark.parametrize("status,expected", [(404, 404), (403, 403), (401, 403), (500, 503)])
def test_service_distinguishes_upstream_errors(status, expected):
    response = Mock(status_code=status)
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    with patch.object(netbox.client, "NETBOX_URL", "https://netbox.example"), patch.object(netbox.requests, "get", return_value=response):
        with pytest.raises(netbox.NetBoxError) as error:
            netbox.get_device(842)
    assert error.value.status == expected


def test_service_rejects_malformed_json():
    response = Mock()
    response.json.side_effect = ValueError("invalid JSON")
    with patch.object(netbox.client, "NETBOX_URL", "https://netbox.example"), patch.object(netbox.requests, "get", return_value=response):
        with pytest.raises(netbox.NetBoxError):
            netbox.get_device(842)


def test_email_renders_snapshot_and_legacy_without_network():
    checklist = Checklist.objects.create(turno="Turno 1")
    external = Ocorrencia.objects.create(checklist=checklist, netbox_object_type="dcim.device", netbox_object_id=842, equipamento_nome="Nome histórico", descricao="Falha")
    legacy = Ocorrencia.objects.create(checklist=checklist, equipamento=mixer.blend(Equipamento))
    with patch.object(netbox.requests, "get") as get:
        html = render_to_string("noc/email/checklist.html", {"checklist": checklist, "ocorrencias_abertas": []})
    get.assert_not_called()
    assert external.equipamento_nome in html
    from django.utils.html import escape
    assert escape(str(legacy.equipamento)) in html


def test_admin_can_add_checklist_with_netbox_occurrence(client):
    user = mixer.blend("colaborador.Colaborador", is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    url = reverse("admin:noc_checklist_add")
    response = client.get(url)
    assert response.status_code == 200
    assert b'noc/netbox-device.js' in response.content
    assert b'data-search-url="/noc/netbox/devices/"' in response.content
    data = {"turno": "Turno 1", "outros": "Teste do turno", "_save": "Salvar"}
    for inline in response.context["inline_admin_formsets"]:
        prefix = inline.formset.prefix
        data.update({f"{prefix}-TOTAL_FORMS": "0", f"{prefix}-INITIAL_FORMS": "0", f"{prefix}-MIN_NUM_FORMS": "0", f"{prefix}-MAX_NUM_FORMS": "1000"})
        if inline.formset.model is Ocorrencia:
            data.update({f"{prefix}-TOTAL_FORMS": "1", f"{prefix}-0-netbox_device": "842", f"{prefix}-0-descricao": "Disco com falha"})
    with patch("apps.noc.forms.get_device", return_value=DEVICE):
        response = client.post(url, data)
    assert response.status_code == 302, response.context and response.context["inline_admin_formsets"][-1].formset.errors
    item = Ocorrencia.objects.get()
    assert item.checklist.turno == "Turno 1"
    assert item.equipamento_nome == "servidor-01"
    assert item.equipamento_id is None
    response = client.get(reverse("admin:noc_checklist_change", args=[item.checklist_id]))
    assert response.status_code == 200
    assert b'servidor-01' in response.content
