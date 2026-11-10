from unittest.mock import Mock, patch

import pytest
from django.urls import reverse
from django.contrib.auth.models import Permission
from mixer.backend.django import mixer
from apps.core.models import GrupoAcesso
from apps.monitoramento.models.nagios import NagiosServicos
from django.apps import apps
from importlib import import_module
from apps.infra.services.server_registration import NetBoxError

from apps.infra.models import Equipamento, Servidor, NetBoxServerOperations, Ocorrencia


@pytest.mark.django_db
def test_netbox_server_page_is_read_only_until_first_operational_save(client):
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    url = reverse('admin:infra_servidor_netbox_operational', args=[42])
    with patch('apps.infra.admin.get_server_detail', return_value={'name': 'srv42', 'model': 'R710', 'status': 'Ativo'}):
        response = client.get(url)
    assert response.status_code == 200
    assert b'srv42' in response.content
    assert b'Grupos de Acesso' in response.content
    assert b'Criar no FreeIPA' in response.content
    assert b'Criar com Conta Local' in response.content
    assert Servidor.objects.count() == 0
    assert Equipamento.objects.count() == 0


@pytest.mark.django_db
def test_first_operational_save_does_not_create_server(client):
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    url = reverse('admin:infra_servidor_netbox_operational', args=[42])
    with patch('apps.infra.admin.get_server_detail', return_value={'name': 'srv42', 'model': 'R710', 'status': 'Ativo'}):
        response = client.post(url, {'tipo_uso': 'OPERACIONAL'})
    assert response.status_code == 302
    assert NetBoxServerOperations.objects.get(netbox_object_type='dcim.device', netbox_object_id=42).tipo_uso == 'OPERACIONAL'
    assert Servidor.objects.count() == 0
    assert Equipamento.objects.count() == 0


@pytest.mark.django_db
def test_group_and_nagios_configuration_uses_netbox_identity(client):
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    group = mixer.blend(GrupoAcesso)
    service = mixer.blend(NagiosServicos)
    url = reverse('admin:infra_servidor_netbox_operational', args=[42])
    with patch('apps.infra.admin.get_server_detail', return_value={'name': 'srv42'}):
        assert client.post(url, {'action': 'add_group', 'group': group.pk}).status_code == 302
        assert client.post(url, {'action': 'add_nagios', 'service': service.pk}).status_code == 302
    operation = NetBoxServerOperations.objects.get(netbox_object_id=42)
    assert list(operation.grupos_acesso.all()) == [group]
    assert list(operation.nagios_servicos.all()) == [service]
    assert Servidor.objects.count() == 0


@pytest.mark.django_db
def test_legacy_links_are_copied_once_without_operating_system():
    server = mixer.blend(Servidor, netbox_object_type='dcim.device', netbox_object_id=42,
                         nome='srv42', status='Em uso', conta='FreeIPA', tipo_uso='OPERACIONAL')
    group = mixer.blend(GrupoAcesso)
    service = mixer.blend(NagiosServicos)
    server.grupos_acesso.add(group)
    server.nagios_servicos.add(service)
    migration = import_module('apps.infra.migrations.0025_copy_netbox_server_operations')
    migration.copy_operations(apps, None)
    migration.copy_operations(apps, None)
    operation = NetBoxServerOperations.objects.get(netbox_object_id=42)
    assert (operation.status, operation.conta, operation.tipo_uso) == ('Em uso', 'FreeIPA', 'OPERACIONAL')
    assert list(operation.grupos_acesso.all()) == [group]
    assert list(operation.nagios_servicos.all()) == [service]
    assert NetBoxServerOperations.objects.count() == 1


@pytest.mark.django_db
def test_inventory_edit_writes_netbox_without_local_server(client):
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    url = reverse('admin:infra_servidor_netbox_operational', args=[42])
    with patch('apps.infra.admin.get_server_detail', return_value={'name': 'srv42', 'serial': 'OLD', 'asset_tag': 'P1', 'description': 'Old'}), \
         patch('apps.infra.admin.update_server_inventory') as update:
        response = client.post(url, {'action': 'update_inventory', 'nome': 'srv43', 'serie': 'SN2',
                                     'patrimonio': 'P2', 'descricao': 'New', 'comentarios': 'Nota'})
    assert response.status_code == 302
    update.assert_called_once_with('dcim.device', 42, {'nome': 'srv43', 'serie': 'SN2', 'patrimonio': 'P2', 'descricao': 'New', 'comentarios': 'Nota'})
    assert Servidor.objects.count() == 0


@pytest.mark.django_db
def test_inventory_edit_reports_netbox_failure(client):
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    url = reverse('admin:infra_servidor_netbox_operational', args=[42])
    with patch('apps.infra.admin.get_server_detail', return_value={'name': 'srv42'}), \
         patch('apps.infra.admin.update_server_inventory', side_effect=NetBoxError('Falha no NetBox')):
        response = client.post(url, {'action': 'update_inventory', 'nome': 'srv43'})
    assert response.status_code >= 400
    assert Servidor.objects.count() == 0


@pytest.mark.django_db
def test_occurrence_is_saved_against_netbox_identity(client):
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    url = reverse('admin:infra_servidor_netbox_operational', args=[42])
    with patch('apps.infra.admin.get_server_detail', return_value={'name': 'srv42'}):
        response = client.post(url, {'action': 'add_occurrence', 'ocorrencia': 'Falha',
                                     'descricao': 'Disco', 'status': 'Aberto'})
    assert response.status_code == 302
    occurrence = Ocorrencia.objects.get()
    assert (occurrence.netbox_object_type, occurrence.netbox_object_id, occurrence.status) == ('dcim.device', 42, 'Aberto')
    assert occurrence.equipamento_id is None
    assert Servidor.objects.count() == 0


@pytest.mark.django_db
def test_occurrence_status_can_be_updated_from_server_page(client):
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    occurrence = Ocorrencia.objects.create(netbox_object_type='dcim.device', netbox_object_id=42,
        equipamento_nome='srv42', ocorrencia='Falha', descricao='Disco', status='Aberto')
    url = reverse('admin:infra_servidor_netbox_operational', args=[42])
    with patch('apps.infra.admin.get_server_detail', return_value={'name': 'srv42'}):
        response = client.post(url, {'action': 'update_occurrence', 'occurrence': occurrence.pk, 'status': 'Fechado'})
    occurrence.refresh_from_db()
    assert response.status_code == 302
    assert occurrence.status == 'Fechado'


@pytest.mark.django_db
def test_occurrence_can_be_removed_without_removing_server(client):
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    occurrence = Ocorrencia.objects.create(netbox_object_type='dcim.device', netbox_object_id=42,
        equipamento_nome='srv42', ocorrencia='Falha', status='Aberto')
    url = reverse('admin:infra_servidor_netbox_operational', args=[42])
    with patch('apps.infra.admin.get_server_detail', return_value={'name': 'srv42'}):
        response = client.post(url, {'action': 'delete_occurrence', 'occurrence': occurrence.pk})
    assert response.status_code == 302
    assert not Ocorrencia.objects.filter(pk=occurrence.pk).exists()
    assert Servidor.objects.count() == 0


@pytest.mark.django_db
def test_status_action_adds_default_nagios_without_local_server(client):
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    service = mixer.blend(NagiosServicos, padrao=True)
    url = reverse('admin:infra_servidor_netbox_operational', args=[42])
    with patch('apps.infra.admin.get_server_detail', return_value={'name': 'srv42'}), \
         patch('apps.infra.admin.send_email_task.delay'):
        response = client.post(url, {'action': 'toggle_status'})
    assert response.status_code == 302
    operation = NetBoxServerOperations.objects.get(netbox_object_id=42)
    assert operation.status == 'Em uso'
    assert list(operation.nagios_servicos.all()) == [service]
    assert Servidor.objects.count() == 0
    assert b'Em uso' in client.get(reverse('admin:infra_servidor_netbox_history', args=[42])).content


@pytest.mark.django_db
def test_local_account_requires_group_and_marks_operation(client):
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    url = reverse('admin:infra_servidor_netbox_operational', args=[42])
    with patch('apps.infra.admin.get_server_detail', return_value={'name': 'srv42'}):
        assert client.post(url, {'action': 'create_local'}).status_code == 400
        assert NetBoxServerOperations.objects.count() == 0
        group = mixer.blend(GrupoAcesso)
        operation = NetBoxServerOperations.objects.create(netbox_object_type='dcim.device', netbox_object_id=42)
        operation.grupos_acesso.add(group)
        with patch('apps.infra.admin.send_email_task.delay'):
            response = client.post(url, {'action': 'create_local'})
    assert response.status_code == 302
    operation.refresh_from_db()
    assert operation.conta == 'Local'
    assert Servidor.objects.count() == 0


@pytest.mark.django_db
def test_freeipa_action_uses_netbox_snapshot_without_creating_server(client):
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    group = mixer.blend(GrupoAcesso)
    operation = NetBoxServerOperations.objects.create(netbox_object_type='dcim.device', netbox_object_id=42)
    operation.grupos_acesso.add(group)
    url = reverse('admin:infra_servidor_netbox_operational', args=[42])
    snapshot = {'nome': 'srv42', 'descricao': 'Servidor', 'netbox_ips': [{'hostname': 'srv42.example.test', 'ip': '192.0.2.42'}]}
    with patch('apps.infra.admin.get_server_detail', return_value={'name': 'srv42'}), \
         patch('apps.infra.admin.get_server_snapshot', return_value=snapshot), \
         patch('apps.infra.admin.FreeIPA') as freeipa, \
         patch('apps.infra.admin.Automount') as automount, \
         patch('apps.infra.admin.send_email_task.delay'):
        freeipa.return_value.set_host.return_value = True
        response = client.post(url, {'action': 'create_freeipa'})
    assert response.status_code == 302
    host = freeipa.return_value.set_host.call_args.args[0]
    assert host.freeipa_name == 'srv42.example.test'
    assert host.enderecos_operacionais == [('srv42.example.test', '192.0.2.42')]
    assert automount.called
    operation.refresh_from_db()
    assert operation.conta == 'FreeIPA'
    assert Servidor.objects.count() == 0


@pytest.mark.django_db
def test_new_group_updates_freeipa_before_saving_relation(client):
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    group = mixer.blend(GrupoAcesso)
    operation = NetBoxServerOperations.objects.create(netbox_object_type='dcim.device', netbox_object_id=42, conta='FreeIPA')
    snapshot = {'nome': 'srv42', 'descricao': '', 'netbox_ips': [{'hostname': 'srv42.example.test', 'ip': '192.0.2.42'}]}
    url = reverse('admin:infra_servidor_netbox_operational', args=[42])
    with patch('apps.infra.admin.get_server_detail', return_value={'name': 'srv42'}), \
         patch('apps.infra.admin.get_server_snapshot', return_value=snapshot), \
         patch('apps.infra.admin.FreeIPA'), patch('apps.infra.admin.Automount') as automount:
        response = client.post(url, {'action': 'add_group', 'group': group.pk})
    assert response.status_code == 302
    automount.return_value.adicionar_grupos.assert_called_once()
    assert list(operation.grupos_acesso.all()) == [group]


@pytest.mark.django_db
def test_parallel_server_registration_is_closed(client):
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    response = client.get(reverse('admin:infra_servidor_add'))
    assert response.status_code == 403


@pytest.mark.django_db
def test_operational_history_shows_local_account_change(client):
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    group = mixer.blend(GrupoAcesso)
    operation = NetBoxServerOperations.objects.create(netbox_object_type='dcim.device', netbox_object_id=42)
    operation.grupos_acesso.add(group)
    url = reverse('admin:infra_servidor_netbox_operational', args=[42])
    with patch('apps.infra.admin.get_server_detail', return_value={'name': 'srv42'}), \
         patch('apps.infra.admin.send_email_task.delay'):
        client.post(url, {'action': 'create_local'})
        response = client.get(reverse('admin:infra_servidor_netbox_history', args=[42]))
    assert response.status_code == 200
    assert b'Conta local criada' in response.content


@pytest.mark.django_db
def test_page_includes_occurrences_from_previously_linked_server(client):
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    server = mixer.blend(Servidor, netbox_object_type='dcim.device', netbox_object_id=42, nome='srv42')
    Ocorrencia.objects.create(equipamento=server, ocorrencia='Legada', descricao='Disco')
    url = reverse('admin:infra_servidor_netbox_operational', args=[42])
    with patch('apps.infra.admin.get_server_detail', return_value={'name': 'srv42'}):
        response = client.get(url)
    assert b'Legada' in response.content


@pytest.mark.django_db
def test_status_counter_does_not_double_count_migrated_server():
    from apps.core.views import CoreStatusView
    mixer.blend(Servidor, netbox_object_type='dcim.device', netbox_object_id=42, nome='srv42', status='Em uso')
    NetBoxServerOperations.objects.create(netbox_object_type='dcim.device', netbox_object_id=42, status='Em uso')
    mixer.blend(Servidor, netbox_object_type='', netbox_object_id=None, nome='legacy', status='Em uso')
    NetBoxServerOperations.objects.create(netbox_object_type='dcim.device', netbox_object_id=43, status='Em uso')
    assert CoreStatusView().get_context_data()['servidor'] == 3


@pytest.mark.django_db
def test_view_only_user_cannot_change_operational_state(client):
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=False)
    user.user_permissions.add(Permission.objects.get(content_type__app_label='infra', codename='view_servidor'))
    client.force_login(user)
    url = reverse('admin:infra_servidor_netbox_operational', args=[42])
    with patch('apps.infra.admin.get_server_detail', return_value={'name': 'srv42'}):
        assert client.get(url).status_code == 200
        assert client.post(url, {'action': 'toggle_status'}).status_code == 403
    assert NetBoxServerOperations.objects.count() == 0


@pytest.mark.django_db
def test_virtual_server_has_separate_list_and_operational_page(client):
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    with patch('apps.infra.admin.search_servers', return_value={'results': [{'id': 7, 'label': 'vm07'}], 'more': False}):
        listing = client.get(reverse('admin:infra_servidor_netbox_vms'))
    assert listing.status_code == 200
    assert b'vm07' in listing.content
    url = reverse('admin:infra_servidor_netbox_vm_operational', args=[7])
    snapshot = {'nome': 'vm07', 'modelo': '', 'patrimonio': '', 'serie': '', 'descricao': '',
                'netbox_localizacao': 'Cluster A', 'netbox_ips': []}
    with patch('apps.infra.admin.get_server_snapshot', return_value=snapshot):
        page = client.get(url)
    assert page.status_code == 200
    assert b'vm07' in page.content
    assert Servidor.objects.count() == 0


def test_virtual_server_detail_keeps_netbox_comments():
    from apps.infra.admin import virtual_server_detail
    snapshot = {'nome': 'vm07', 'modelo': '', 'patrimonio': '', 'serie': '', 'descricao': '',
                'comments': 'Contato da VM', 'netbox_localizacao': 'Cluster A', 'netbox_ips': []}
    with patch('apps.infra.admin.get_server_snapshot', return_value=snapshot):
        assert virtual_server_detail(7)['comments'] == 'Contato da VM'


@pytest.mark.django_db
def test_virtual_server_occurrence_has_valid_netbox_reference():
    from apps.infra.services.server_registration import VIRTUAL
    occurrence = Ocorrencia(netbox_object_type=VIRTUAL, netbox_object_id=7,
        equipamento_nome='vm07', ocorrencia='Falha', status='Aberto')
    occurrence.full_clean()


@pytest.mark.django_db
def test_vm_target_reloads_from_netbox_identity():
    from apps.infra.services.netbox_vm import load_vm_target
    from apps.infra.services.server_registration import VIRTUAL
    operation = NetBoxServerOperations.objects.create(netbox_object_type=VIRTUAL, netbox_object_id=7, tipo_uso='OPERACIONAL')
    snapshot = {'nome': 'vm07', 'descricao': 'VM', 'netbox_ips': [{'hostname': 'vm07.example.test', 'ip': '192.0.2.7'}]}
    with patch('apps.infra.services.netbox_vm.get_server_snapshot', return_value=snapshot):
        target = load_vm_target(7)
    assert target.id == [VIRTUAL, 7]
    assert target.host_principal == ('vm07.example.test', '192.0.2.7')
    assert target.tipo_uso == operation.tipo_uso


@pytest.mark.django_db
def test_vm_completion_can_be_recorded_on_operations():
    from apps.infra.services.server_registration import VIRTUAL
    from apps.infra.models import AmbienteVirtual
    environment = mixer.blend(AmbienteVirtual)
    operation = NetBoxServerOperations.objects.create(netbox_object_type=VIRTUAL, netbox_object_id=7)
    operation.vm_remover = True
    operation.vm_ambiente_virtual = environment
    operation.save()
    operation = NetBoxServerOperations.objects.get(pk=operation.pk)
    assert operation.vm_remover is True
    assert operation.vm_ambiente_virtual == environment


@pytest.mark.django_db
def test_vm_worker_resolves_reference_without_local_server():
    from apps.infra.tasks import resolve_vm_destination
    from apps.infra.services.server_registration import VIRTUAL
    snapshot = {'nome': 'vm07', 'descricao': 'VM', 'netbox_ips': [{'hostname': 'vm07.example.test', 'ip': '192.0.2.7'}]}
    NetBoxServerOperations.objects.create(netbox_object_type=VIRTUAL, netbox_object_id=7)
    with patch('apps.infra.services.netbox_vm.get_server_snapshot', return_value=snapshot):
        target = resolve_vm_destination([VIRTUAL, 7])
    assert target.nome == 'vm07'
    assert Servidor.objects.count() == 0


@pytest.mark.django_db
def test_vm_page_starts_provisioning_with_netbox_reference(client):
    from apps.infra.services.server_registration import VIRTUAL
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    template = mixer.blend('infra.TemplateVM')
    NetBoxServerOperations.objects.create(netbox_object_type=VIRTUAL, netbox_object_id=7, conta='Local')
    snapshot = {'nome': 'vm07', 'modelo': '', 'patrimonio': '', 'serie': '', 'descricao': 'VM',
                'netbox_localizacao': 'Cluster A', 'netbox_ips': [{'hostname': 'vm07.example.test', 'ip': '192.0.2.7'}]}
    url = reverse('admin:infra_servidor_netbox_vm_operational', args=[7])
    with patch('apps.infra.admin.get_server_snapshot', return_value=snapshot), \
         patch('apps.infra.services.netbox_vm.get_server_snapshot', return_value=snapshot), \
         patch('apps.infra.admin.XenCrud') as xen:
        xen.return_value.create_vm.return_value = Mock(id='task-123')
        response = client.post(url, {'action': 'create_vm', 'template': template.pk, 'memoria': '8', 'cpu': '4'})
    assert response.status_code == 302
    assert 'task-123' in response.url
    assert xen.called
    assert Servidor.objects.count() == 0


@pytest.mark.django_db
def test_vm_legacy_state_is_migrated():
    from apps.infra.services.server_registration import VIRTUAL
    from apps.infra.models import AmbienteVirtual
    environment = mixer.blend(AmbienteVirtual)
    mixer.blend(Servidor, netbox_object_type=VIRTUAL, netbox_object_id=7,
                nome='vm07', vm_remover=True, vm_ambiente_virtual=environment)
    operation = NetBoxServerOperations.objects.create(netbox_object_type=VIRTUAL, netbox_object_id=7)
    migration = import_module('apps.infra.migrations.0027_copy_netbox_vm_state')
    migration.copy_vm_state(apps, None)
    operation.refresh_from_db()
    assert operation.vm_remover is True
    assert operation.vm_ambiente_virtual == environment


@pytest.mark.django_db
def test_vm_removal_action_keeps_netbox_operations_record(client):
    from apps.infra.services.server_registration import VIRTUAL
    user = mixer.blend('colaborador.Colaborador', is_active=True, is_staff=True, is_superuser=True)
    client.force_login(user)
    environment = mixer.blend('infra.AmbienteVirtual')
    operation = NetBoxServerOperations.objects.create(netbox_object_type=VIRTUAL, netbox_object_id=7,
        conta='Local', vm_remover=True, vm_ambiente_virtual=environment)
    snapshot = {'nome': 'vm07', 'modelo': '', 'patrimonio': '', 'serie': '', 'descricao': 'VM',
                'netbox_localizacao': 'Cluster A', 'netbox_ips': [{'hostname': 'vm07.example.test', 'ip': '192.0.2.7'}]}
    url = reverse('admin:infra_servidor_netbox_vm_operational', args=[7])
    with patch('apps.infra.admin.get_server_snapshot', return_value=snapshot), \
         patch('apps.infra.services.netbox_vm.get_server_snapshot', return_value=snapshot), \
         patch('apps.infra.admin.XenCrud') as xen:
        xen.return_value.delete_vm.return_value = Mock(id='delete-task')
        response = client.post(url, {'action': 'delete_vm'})
    assert response.status_code == 302
    assert xen.return_value.delete_vm.called
    assert NetBoxServerOperations.objects.filter(pk=operation.pk).exists()
    assert Servidor.objects.count() == 0


def test_xen_delete_task_receives_netbox_vm_reference():
    from apps.infra.utils.xen_crud import XenCrud
    from apps.infra.services.server_registration import VIRTUAL
    xen = XenCrud.__new__(XenCrud)
    xen.vm = Mock(nome='vm07', id=[VIRTUAL, 7])
    xen.servidor = '192.0.2.1'
    xen.request = Mock()
    with patch.object(xen, 'login'), patch('apps.infra.utils.xen_crud.delete_vm_task.delay') as delay:
        xen.delete_vm()
    delay.assert_called_once_with('192.0.2.1', 'vm07', [VIRTUAL, 7])
