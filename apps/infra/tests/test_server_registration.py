from unittest.mock import patch, Mock

import pytest
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.urls import reverse
from mixer.backend.django import mixer

from apps.core.models import GrupoAcesso, Tenants, OperatingSystem
from apps.infra.forms import NetBoxServidorForm
from apps.infra.models import Servidor, HostnameIP, Rede, EquipamentoGrupoAcesso
from apps.infra.services.server_registration import get_server_snapshot, search_servers, NetBoxError

pytestmark = pytest.mark.django_db
PHYSICAL = 'dcim.device'
VIRTUAL = 'virtualization.virtualmachine'
SNAPSHOT = {'nome': 'srv01', 'tipo': 'Servidor Físico', 'marca': 'Dell', 'modelo': 'R710', 'serie': 'SN1', 'patrimonio': 'PAT1', 'descricao': 'Servidor NetBox', 'netbox_localizacao': 'CPT / R01', 'netbox_ips': [{'hostname': 'srv01.example.test', 'ip': '192.0.2.10'}]}


def data(kind=PHYSICAL, id=42):
    return {'netbox_tipo': kind, 'netbox_device': str(id), 'tipo_uso': 'OPERACIONAL', 'servicos': 'Uso operacional'}


def register(kind=PHYSICAL, id=42):
    snapshot={**SNAPSHOT, 'tipo': 'Servidor Virtual' if kind == VIRTUAL else 'Servidor Físico'}
    with patch('apps.infra.forms.get_server_snapshot', return_value=snapshot):
        form=NetBoxServidorForm(data=data(kind,id))
        assert form.is_valid(), form.errors
        return form.save()


@pytest.mark.parametrize('kind',[PHYSICAL,VIRTUAL])
def test_registers_operational_reference_without_manual_inventory(kind):
    before=HostnameIP.objects.count(),Rede.objects.count()
    item=register(kind)
    item.refresh_from_db()
    assert (item.netbox_object_type,item.netbox_object_id)==(kind,42)
    assert item.nome=='srv01' and item.patrimonio=='PAT1'
    assert item.tipo==('Servidor Virtual' if kind==VIRTUAL else 'Servidor Físico')
    assert item.host_principal==('srv01.example.test','192.0.2.10')
    assert before==(HostnameIP.objects.count(),Rede.objects.count())
    assert item.netbox_atualizado_em


def test_editable_inventory_fields_update_netbox_but_identity_stays_fixed():
    posted={**data(),'nome':'novo','marca':'fake','patrimonio':'PAT2','tipo':'Servidor Virtual','netbox_object_id':'99'}
    with patch('apps.infra.forms.get_server_snapshot',return_value=SNAPSHOT), \
         patch('apps.infra.forms.update_server_inventory') as update:
        form=NetBoxServidorForm(data=posted)
        assert form.is_valid(),form.errors
        item=form.save()
    update.assert_called_once_with(PHYSICAL,42,{'nome':'novo','patrimonio':'PAT2'})
    assert item.nome=='novo' and item.patrimonio=='PAT2' and item.netbox_object_id==42


def test_duplicate_reference_rejected_but_ids_in_different_types_are_allowed():
    register()
    with patch('apps.infra.forms.get_server_snapshot',return_value=SNAPSHOT):
        form=NetBoxServidorForm(data=data())
        assert not form.is_valid()
    assert register(VIRTUAL).netbox_object_id==42


def test_edit_operational_fields_offline_preserves_groups_tenants_and_systems():
    item=register()
    group=mixer.blend(GrupoAcesso)
    EquipamentoGrupoAcesso.objects.create(equipamento=item,grupo_acesso=group)
    tenant=Tenants.objects.create(tenants='Operação')
    os=OperatingSystem.objects.create(so='Linux')
    item.tenants.add(tenant)
    item.so.add(os)
    with patch('apps.infra.forms.get_server_snapshot') as get:
        form=NetBoxServidorForm(data={**data(),'servicos':'Alterado'},instance=item)
        assert form.is_valid(),form.errors
        form.save()
    get.assert_not_called()
    item.refresh_from_db()
    assert item.servicos=='Alterado' and item.nome=='srv01'
    assert item.grupos_acesso.get()==group and item.tenants.get()==tenant and item.so.get()==os


def test_cannot_reassign_existing_external_identity():
    item=register()
    form=NetBoxServidorForm(data=data(id=99),instance=item)
    assert not form.is_valid()


def test_refresh_updates_inventory_and_preserves_operational_status():
    item=register()
    item.status='Em uso'
    item.save()
    with patch('apps.infra.forms.get_server_snapshot',return_value={**SNAPSHOT,'modelo':'R750'}):
        form=NetBoxServidorForm(data={**data(),'atualizar_netbox':'on'},instance=item)
        assert form.is_valid(),form.errors
        form.save()
    item.refresh_from_db()
    assert item.modelo=='R750' and item.status=='Em uso'


def test_refresh_failure_does_not_erase_saved_data():
    item=register()
    with patch('apps.infra.forms.get_server_snapshot',side_effect=NetBoxError('Indisponível')):
        form=NetBoxServidorForm(data={**data(),'atualizar_netbox':'on'},instance=item)
        assert not form.is_valid()
    item.refresh_from_db()
    assert item.nome=='srv01' and item.netbox_ips==SNAPSHOT['netbox_ips']


def test_old_server_can_be_edited_without_external_reference_or_hostname_lookup():
    item=mixer.blend(Servidor,nome='antigo',netbox_object_type='',netbox_object_id=None,netbox_ips=[])
    with patch('apps.infra.forms.get_server_snapshot') as get:
        form=NetBoxServidorForm(data={'netbox_tipo':PHYSICAL,'tipo_uso':'OPERACIONAL','servicos':'Atualizado'},instance=item)
        assert form.is_valid(),form.errors
        form.save()
    get.assert_not_called()
    assert item.nome=='antigo' and item.servicos=='Atualizado'


@pytest.mark.parametrize('kind,id',[('',42),('ipam.prefix',42),(PHYSICAL,0),(PHYSICAL,None)])
def test_model_rejects_partial_or_invalid_reference(kind,id):
    item=Servidor(netbox_object_type=kind,netbox_object_id=id)
    with pytest.raises(ValidationError):
        item.clean()


def test_source_search_requires_server_permission_not_noc(client):
    url=reverse('admin:infra_servidor_netbox_search')
    assert client.get(url).status_code==302
    user=mixer.blend('colaborador.Colaborador',is_active=True,is_staff=True,is_superuser=False)
    client.force_login(user)
    assert client.get(url).status_code==403
    user.user_permissions.add(Permission.objects.get(content_type__app_label='infra',codename='view_servidor'))
    with patch('apps.infra.admin.search_servers',return_value={'results':[],'more':False}) as search:
        assert client.get(url,{'object_type':VIRTUAL}).status_code==200
    search.assert_called_once_with(VIRTUAL,'',0)


def test_admin_creation_uses_new_form_and_does_not_reserve_hostname(client):
    user=mixer.blend('colaborador.Colaborador',is_active=True,is_staff=True,is_superuser=True)
    client.force_login(user)
    url=reverse('admin:infra_servidor_add')
    response=client.get(url)
    assert response.status_code==403
    assert Servidor.objects.count()==0
    assert HostnameIP.objects.count()==0


def test_netbox_card_opens_operational_form_without_creating_record(client):
    user=mixer.blend('colaborador.Colaborador',is_active=True,is_staff=True,is_superuser=True)
    client.force_login(user)
    url=reverse('admin:infra_servidor_netbox_operational',args=[42])
    with patch('apps.infra.admin.get_server_detail',return_value={'name':'srv01'}):
        response=client.get(url)
    assert response.status_code==200
    assert b'srv01' in response.content
    assert Servidor.objects.count()==0


def test_netbox_card_first_save_creates_one_operational_record(client):
    user=mixer.blend('colaborador.Colaborador',is_active=True,is_staff=True,is_superuser=True)
    client.force_login(user)
    url=reverse('admin:infra_servidor_netbox_operational',args=[42])
    with patch('apps.infra.admin.get_server_detail',return_value={'name':'srv01'}):
        response=client.post(url,{'tipo_uso':'OPERACIONAL'})
    assert response.status_code==302
    from apps.infra.models import NetBoxServerOperations
    assert NetBoxServerOperations.objects.get(netbox_object_id=42).tipo_uso=='OPERACIONAL'
    assert Servidor.objects.count()==0


def test_inventory_update_writes_only_editable_fields():
    from apps.infra.services import server_registration
    response=Mock(status_code=200)
    response.json.return_value={'id':42,'name':'novo'}
    with patch('apps.infra.services.server_registration.requests.patch',return_value=response) as patch_request, \
         patch('apps.infra.services.server_registration.client.NETBOX_URL','https://netbox.example'), \
         patch('apps.infra.services.server_registration.client.NETBOX_TOKEN','token'):
        server_registration.update_server_inventory(PHYSICAL,42,{'nome':'novo','serie':'S2','patrimonio':'P2','descricao':'editado'})
    assert patch_request.call_args.kwargs['json']=={'name':'novo','serial':'S2','asset_tag':'P2','description':'editado'}
    assert patch_request.call_args.args[0]=='https://netbox.example/api/dcim/devices/42/'


def test_netbox_write_failure_does_not_save_local_change():
    item=register()
    with patch('apps.infra.forms.update_server_inventory',side_effect=NetBoxError('Sem permissão')):
        form=NetBoxServidorForm(data={**data(),'nome':'alterado'},instance=item)
        assert not form.is_valid()
    item.refresh_from_db()
    assert item.nome=='srv01'


def test_snapshot_validates_role_and_reads_all_ips():
    device={'id':42,'name':'srv01','role':{'slug':'server'},'primary_ip4':{'address':'192.0.2.10/24','dns_name':'srv01.example.test'},'device_type':{'model':'R710','manufacturer':{'name':'Dell'}}}
    with patch('apps.infra.services.server_registration._get',side_effect=[device,{'results':[{'address':'192.0.2.11/24','dns_name':'srv01-other'}],'next':None}]) as get:
        snapshot=get_server_snapshot(PHYSICAL,42)
    assert [ip['ip'] for ip in snapshot['netbox_ips']]==['192.0.2.10','192.0.2.11']
    assert snapshot['modelo']=='R710'
    assert 'device_id=42' in get.call_args.args[0]
    with patch('apps.infra.services.server_registration._get',return_value={**device,'role':{'slug':'storage'}}):
        with pytest.raises(NetBoxError):
            get_server_snapshot(PHYSICAL,42)


def test_vm_snapshot_uses_vm_endpoint_and_ipv6():
    with patch('apps.infra.services.server_registration._get',side_effect=[{'id':42,'name':'vm01','primary_ip6':{'address':'2001:db8::1/64'}},{'results':[],'next':None}]) as get:
        snapshot=get_server_snapshot(VIRTUAL,42)
    assert get.call_args_list[0].args[0]=='virtualization/virtual-machines/42/'
    assert snapshot['tipo']=='Servidor Virtual'
    assert snapshot['netbox_ips'][0]['ip']=='2001:db8::1'


def test_new_source_without_ips_has_clear_operational_error():
    item=register()
    item.netbox_ips=[]
    with pytest.raises(OSError,match='IP'):
        _=item.host_principal


def test_vm_commands_use_netbox_addresses_without_hostname_rows():
    from types import SimpleNamespace
    from apps.infra.tasks import get_comandos
    vm=register(VIRTUAL)
    template=Mock()
    template.host_principal=('template','192.0.2.1')
    template.origens.all.return_value=[SimpleNamespace(ip='192.0.2.1')]
    template.template_comandos.all.return_value.exclude.return_value=[]
    template.template_comandos.filter.return_value=[SimpleNamespace(comando='src={template_origem_ip} dst={vm_ip}',configuracao=2)]
    assert get_comandos(template,vm)['2']==['src=192.0.2.1 dst=192.0.2.10']


def test_xen_connection_uses_netbox_host_ip_without_network_io():
    from apps.infra.models import AmbienteVirtual
    from apps.infra.utils.xen_crud import XenCrud
    host=register()
    pool=mixer.blend(AmbienteVirtual)
    pool.servidor.add(host)
    client=XenCrud(Mock(),Mock(),pool)
    assert client.servidor=='192.0.2.10'


@pytest.mark.parametrize('prefix',['192.0.2','192.0.2.0/24'])
def test_automount_keeps_operational_network_rules_with_netbox_ips(prefix):
    from apps.infra.utils.freeipa_location import Automount
    host=register()
    network=Rede.objects.create(rede='Operacional',ip=prefix,prioridade_montagem=1)
    assert Automount(Mock(),host,Mock()).rede==network


def test_legacy_primary_hostname_behavior_is_preserved():
    from apps.infra.models import ServidorHostnameIP
    host=mixer.blend(Servidor,netbox_object_id=None,netbox_object_type='',netbox_ips=[])
    address=HostnameIP.objects.create(hostname='legado',ip='150.163.1.2')
    ServidorHostnameIP.objects.create(servidor=host,hostnameip=address)
    assert host.host_principal==('legado','150.163.1.2')


def test_admin_operational_inlines_keep_access_groups_tenants_and_os(client):
    from apps.core.models import ServidorTenants, ServidorOperatingSystem
    user=mixer.blend('colaborador.Colaborador',is_active=True,is_staff=True,is_superuser=True)
    client.force_login(user)
    item=register()
    group=mixer.blend(GrupoAcesso)
    tenant=Tenants.objects.create(tenants='Produção')
    os=OperatingSystem.objects.create(so='Linux')
    url=reverse('admin:infra_servidor_change',args=[item.pk])
    response=client.get(url)
    posted={**data(),'_continue':'Salvar'}
    for inline in response.context['inline_admin_formsets']:
        prefix=inline.formset.prefix
        posted.update({f'{prefix}-TOTAL_FORMS':'0',f'{prefix}-INITIAL_FORMS':'0',f'{prefix}-MIN_NUM_FORMS':'0',f'{prefix}-MAX_NUM_FORMS':'1000'})
        field_value={EquipamentoGrupoAcesso:('grupo_acesso',group.pk),ServidorTenants:('tenant',tenant.pk),ServidorOperatingSystem:('so',os.pk)}.get(inline.formset.model)
        if field_value:
            field,value=field_value
            posted.update({f'{prefix}-TOTAL_FORMS':'1',f'{prefix}-0-{field}':value})
    with patch('apps.infra.forms.get_server_snapshot') as get:
        response=client.post(url,posted)
    assert response.status_code==302
    get.assert_not_called()
    assert EquipamentoGrupoAcesso.objects.filter(equipamento=item,grupo_acesso=group).exists()
    assert ServidorTenants.objects.filter(servidor=item,tenant=tenant).exists()
    assert ServidorOperatingSystem.objects.filter(servidor=item,so=os).exists()


def test_read_only_server_admin_renders_without_editing_fields(client):
    item=register()
    user=mixer.blend('colaborador.Colaborador',is_active=True,is_staff=True,is_superuser=False)
    user.user_permissions.add(Permission.objects.get(content_type__app_label='infra',codename='view_servidor'))
    client.force_login(user)
    response=client.get(reverse('admin:infra_servidor_change',args=[item.pk]))
    assert response.status_code==200
    assert b'srv01' in response.content and b'PAT1' in response.content
    assert b'name="netbox_device"' not in response.content


def test_primary_ip_uses_full_dns_record_without_losing_priority():
    device={'id':42,'name':'Etiqueta do servidor','role':{'slug':'server'},'primary_ip4':{'address':'192.0.2.10/24'}}
    page={'results':[{'address':'192.0.2.11/24','dns_name':'secundario.test'},{'address':'192.0.2.10/24','dns_name':'srv01.example.test'}],'next':None}
    with patch('apps.infra.services.server_registration._get',side_effect=[device,page]):
        snapshot=get_server_snapshot(PHYSICAL,42)
    assert snapshot['netbox_ips'][0]=={'hostname':'srv01.example.test','ip':'192.0.2.10'}


def test_read_only_legacy_server_and_operational_list_are_available(client):
    item=mixer.blend(Servidor,nome='legado',netbox_object_type='',netbox_object_id=None,netbox_ips=[])
    user=mixer.blend('colaborador.Colaborador',is_active=True,is_staff=True,is_superuser=False)
    user.user_permissions.add(Permission.objects.get(content_type__app_label='infra',codename='view_servidor'))
    client.force_login(user)
    assert client.get(reverse('admin:infra_servidor_change',args=[item.pk])).status_code==200
    response=client.get(reverse('admin:infra_servidor_operacionais'))
    assert response.status_code==200 and b'legado' in response.content


def test_vm_clone_uses_the_same_label_as_lookup_and_delete():
    from apps.infra.tasks import create_vm_task
    vm=register(VIRTUAL)
    template=Mock(nome='template')
    template.host_principal=('template','192.0.2.1')
    session=Mock()
    session.xenapi.VM.get_by_name_label.return_value=['template-ref']
    session.xenapi.VM.clone.side_effect=RuntimeError('stop after clone assertion')
    with patch('apps.infra.tasks.get_object_or_404',side_effect=[template,vm]), patch('apps.infra.tasks.Session',return_value=session), patch('apps.infra.tasks.ProgressRecorder'), patch.object(create_vm_task,'update_state'), patch('apps.infra.tasks.send_mail'):
        create_vm_task.run('192.0.2.2',vm.pk,1,'8','4')
    session.xenapi.VM.clone.assert_called_once_with('template-ref',vm.nome)


def test_guest_hostname_placeholder_uses_dns_and_not_inventory_label():
    from types import SimpleNamespace
    from apps.infra.tasks import get_comandos
    vm=register(VIRTUAL)
    vm.nome='Etiqueta VM'
    template=Mock()
    template.host_principal=('template','192.0.2.1')
    template.origens.all.return_value=[]
    template.template_comandos.all.return_value.exclude.return_value=[SimpleNamespace(comando='hostname {vm}',configuracao=1)]
    assert get_comandos(template,vm)['1']==['hostname srv01.example.test']


def test_missing_automount_rule_is_a_form_error_before_freeipa_actions():
    item=register()
    item.conta='FreeIPA'
    item.save()
    form=NetBoxServidorForm(data=data(),instance=item)
    with patch('apps.infra.forms.get_server_snapshot') as get:
        assert not form.is_valid()
    get.assert_not_called()
    assert 'montagem' in str(form.non_field_errors())
