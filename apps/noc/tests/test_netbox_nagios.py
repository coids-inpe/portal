from unittest.mock import patch

import pytest
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.template.loader import render_to_string
from django.urls import reverse
from mixer.backend.django import mixer

from apps.infra.models import Equipamento, ServidorNagiosServico
from apps.monitoramento.models import NagiosServicos
from apps.noc.forms import ChecklistServidorNagiosServicoInlineForm
from apps.noc.models import Checklist, ChecklistServidorNagiosServico
from apps.noc.netbox import NetBoxError

pytestmark = pytest.mark.django_db
DEVICE = {"id": 842, "name": "servidor-01"}


@pytest.fixture
def service():
    return NagiosServicos.objects.create(servico="Ping", comando="check_ping", tempo=5)


def create_alert(service):
    checklist = Checklist.objects.create(turno="Turno 1")
    with patch("apps.noc.forms.get_device", return_value=DEVICE):
        form = ChecklistServidorNagiosServicoInlineForm(data={"netbox_device": "842", "nagios_servico": service.pk})
        assert form.is_valid(), form.errors
        item = form.save(commit=False)
        item.checklist = checklist
        item.save()
    return item


def test_new_alert_uses_netbox_and_existing_service_without_local_server(service):
    before = Equipamento.objects.count(), ServidorNagiosServico.objects.count()
    item = create_alert(service)
    item.refresh_from_db()
    assert item.alerta_monitoramento_id is None
    assert (item.netbox_object_type, item.netbox_object_id, item.equipamento_nome) == ("dcim.device", 842, "servidor-01")
    assert item.nagios_servico_id == service.pk
    assert item.servico_nome == "Ping"
    assert before == (Equipamento.objects.count(), ServidorNagiosServico.objects.count())


@pytest.mark.parametrize("device,svc", [("", ""), ("842", ""), ("", "service"), ("-1", "service"), ("abc", "service"), ("842", "999999")])
def test_new_alert_requires_valid_equipment_and_service(service, device, svc):
    with patch("apps.noc.forms.get_device", return_value=DEVICE):
        form = ChecklistServidorNagiosServicoInlineForm(data={"netbox_device": device, "nagios_servico": service.pk if svc == "service" else svc})
        assert not form.is_valid()


def test_legacy_alert_is_preserved_offline():
    old = mixer.blend(ServidorNagiosServico)
    item = ChecklistServidorNagiosServico.objects.create(checklist=Checklist.objects.create(turno="Turno 1"), alerta_monitoramento=old)
    with patch("apps.noc.forms.get_device") as get:
        form = ChecklistServidorNagiosServicoInlineForm(data={"netbox_device": "", "nagios_servico": ""}, instance=item)
        assert form.is_valid(), form.errors
        form.save()
    get.assert_not_called()
    item.refresh_from_db()
    assert item.alerta_monitoramento_id == old.pk
    assert item.identificacao == str(old)


def test_legacy_alert_can_be_explicitly_reassociated(service):
    old = mixer.blend(ServidorNagiosServico)
    item = ChecklistServidorNagiosServico.objects.create(checklist=Checklist.objects.create(turno="Turno 1"), alerta_monitoramento=old)
    with patch("apps.noc.forms.get_device", return_value=DEVICE):
        form = ChecklistServidorNagiosServicoInlineForm(data={"netbox_device": "842", "nagios_servico": service.pk}, instance=item)
        assert form.is_valid(), form.errors
        form.save()
    assert item.alerta_monitoramento_id is None
    assert ServidorNagiosServico.objects.filter(pk=old.pk).exists()


def test_external_alert_keeps_historical_names_without_network(service):
    item = create_alert(service)
    service.servico = "Ping renomeado"
    service.save()
    with patch("apps.noc.forms.get_device") as get:
        form = ChecklistServidorNagiosServicoInlineForm(data={"netbox_device": "842", "nagios_servico": service.pk}, instance=item)
        assert form.is_valid(), form.errors
        form.save()
    get.assert_not_called()
    item.refresh_from_db()
    assert item.equipamento_nome == "servidor-01"
    assert item.servico_nome == "Ping"


def test_api_failure_preserves_existing_reference(service):
    item = create_alert(service)
    with patch("apps.noc.forms.get_device", side_effect=NetBoxError("NetBox indisponível.")):
        form = ChecklistServidorNagiosServicoInlineForm(data={"netbox_device": "843", "nagios_servico": service.pk}, instance=item)
        assert not form.is_valid()
        assert "netbox_device" in form.errors
    item.refresh_from_db()
    assert item.netbox_object_id == 842


def test_external_alert_cannot_be_cleared(service):
    item = create_alert(service)
    form = ChecklistServidorNagiosServicoInlineForm(data={"netbox_device": "", "nagios_servico": ""}, instance=item)
    assert not form.is_valid()


def test_model_rejects_two_sources_and_incomplete_reference(service):
    checklist = Checklist.objects.create(turno="Turno 1")
    with pytest.raises(ValidationError):
        ChecklistServidorNagiosServico(checklist=checklist).full_clean()
    with pytest.raises(ValidationError):
        ChecklistServidorNagiosServico(checklist=checklist, alerta_monitoramento=mixer.blend(ServidorNagiosServico), nagios_servico=service, netbox_object_type="dcim.device", netbox_object_id=842, equipamento_nome="Servidor", servico_nome="Ping").full_clean()


def test_mixed_alerts_render_in_email_without_network(service):
    external = create_alert(service)
    old = mixer.blend(ServidorNagiosServico)
    ChecklistServidorNagiosServico.objects.create(checklist=external.checklist, alerta_monitoramento=old)
    with patch("apps.noc.forms.get_device") as get:
        html = render_to_string("noc/email/checklist.html", {"checklist": external.checklist, "ocorrencias_abertas": []})
    get.assert_not_called()
    from django.utils.html import escape
    assert "servidor-01" in html and "Ping" in html
    assert escape(str(old)) in html
    assert external.checklist.alerta_monitoramento.get() == old


def test_service_with_new_historical_reference_is_protected(service):
    create_alert(service)
    with pytest.raises(ProtectedError):
        service.delete()


def test_alert_editor_can_search_netbox_without_occurrence_permissions(client):
    user = mixer.blend("colaborador.Colaborador", is_active=True, is_staff=True, is_superuser=False)
    user.user_permissions.add(Permission.objects.get(codename="add_checklist", content_type__app_label="noc"), Permission.objects.get(codename="add_checklistservidornagiosservico", content_type__app_label="noc"))
    client.force_login(user)
    with patch("apps.noc.views.search_devices", return_value={"results": [], "more": False}):
        assert client.get(reverse("noc:netbox_devices")).status_code == 200


def test_admin_creates_and_edits_alert_and_supports_read_only_view(client, service):
    user = mixer.blend("colaborador.Colaborador", is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    url = reverse("admin:noc_checklist_add")
    response = client.get(url)
    assert response.status_code == 200
    data = {"turno": "Turno 2", "outros": "Alerta NetBox", "_save": "Salvar"}
    for inline in response.context["inline_admin_formsets"]:
        prefix = inline.formset.prefix
        data.update({f"{prefix}-TOTAL_FORMS": "0", f"{prefix}-INITIAL_FORMS": "0", f"{prefix}-MIN_NUM_FORMS": "0", f"{prefix}-MAX_NUM_FORMS": "1000"})
        if inline.formset.model is ChecklistServidorNagiosServico:
            data.update({f"{prefix}-TOTAL_FORMS": "1", f"{prefix}-0-netbox_device": "842", f"{prefix}-0-nagios_servico": service.pk})
    with patch("apps.noc.forms.get_device", return_value=DEVICE):
        response = client.post(url, data)
    assert response.status_code == 302
    item = ChecklistServidorNagiosServico.objects.get()
    change_url = reverse("admin:noc_checklist_change", args=[item.checklist_id])
    assert b"servidor-01" in client.get(change_url).content
    viewer = mixer.blend("colaborador.Colaborador", is_active=True, is_staff=True, is_superuser=False)
    viewer.user_permissions.add(Permission.objects.get(codename="view_checklist", content_type__app_label="noc"), Permission.objects.get(codename="view_checklistservidornagiosservico", content_type__app_label="noc"))
    client.force_login(viewer)
    response = client.get(change_url)
    assert response.status_code == 200
    assert b"servidor-01" in response.content and b"Ping" in response.content


def test_add_only_editor_has_equipment_and_service_fields(client, service):
    user = mixer.blend("colaborador.Colaborador", is_active=True, is_staff=True, is_superuser=False)
    user.user_permissions.add(Permission.objects.get(codename="add_checklist", content_type__app_label="noc"), Permission.objects.get(codename="add_checklistservidornagiosservico", content_type__app_label="noc"))
    client.force_login(user)
    response = client.get(reverse("admin:noc_checklist_add"))
    assert response.status_code == 200
    assert b'name="checklistservidornagiosservico_set-__prefix__-netbox_device"' in response.content
    assert b'name="checklistservidornagiosservico_set-__prefix__-nagios_servico"' in response.content
