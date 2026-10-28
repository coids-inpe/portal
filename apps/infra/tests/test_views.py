import pytest
from django.contrib.auth.models import AnonymousUser, Group, Permission, User
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ValidationError
from django.http import Http404
from django.test import RequestFactory
from django.urls import reverse
from mixer.backend.django import mixer

from apps.colaborador.models import Colaborador
from apps.core.models import ( GrupoAcesso, Predio,
                              ResponsavelGrupoTrabalho)
from apps.core.utils.freeipa import FreeIPA
from apps.core.utils.history import HistoryCore
from apps.core.views import UpdateGrupoAcesso
from apps.infra.models import ( Equipamento,
                               EquipamentoGrupoAcesso, EquipamentoParte,
                               HostnameIP, Rede, Servidor,
                               ServidorHostnameIP,
                               StorageGrupoAcessoMontagem)
from apps.infra.views import CriarServidorLdapView
from apps.core.tests.base import *

pytestmark = pytest.mark.django_db



@pytest.fixture
def responsavel(db) -> Colaborador:
    responsavel = mixer.blend(Colaborador, first_name="Responsavel", last_name="Fulano de tal", externo=False, email="teste.reponsavel@inpe.br")
    responsavel.username = None
    responsavel.clean()
    responsavel.groups.add(Group.objects.get(name="Responsavel"))
    responsavel.save()
    return responsavel


def test_criar_servidor_error_view(superuser, grupo_trabalho, responsavel_grupo):
    responsavel_grupo_trabalho = mixer.blend(ResponsavelGrupoTrabalho, grupo=grupo_trabalho, responsavel=responsavel_grupo)
    responsavel_grupo_trabalho.save()

    rede = mixer.blend(Rede, rede="rede", ip='192.168.0', id=2)
    hostnameip = mixer.blend(HostnameIP, hostname='server1', ip='192.168.0.2', tipo=rede)
    hostnameip.save()

    servidor = mixer.blend(Servidor, nome='server1', descricao="Servidor de TESTE")
    servidor.save()
    servidor_host = mixer.blend(ServidorHostnameIP, servidor=servidor, hostnameip=hostnameip)
    servidor_host.save()

    request = RequestFactory().get(reverse("infra:criar_servidor_ldap", kwargs={"pk": servidor.pk}))
    request = message_middleware(request)
    request.user = superuser
    response = CriarServidorLdapView.as_view()(request, pk=servidor.pk)
    assert response.status_code == 302
    assert FreeIPA(request).host_find_count(fqdn=servidor.freeipa_name) == 0


def test_criar_servidor_view(superuser, grupo_trabalho, responsavel_grupo):

    rede = mixer.blend(Rede, rede="rede", ip='192.168.0', prioridade_montagem=1)
    mixer.blend(StorageGrupoAcessoMontagem, ip='192.168.0.1', parametro='-fstype=nfs4,rw', tipo='OPERACIONAL', montagem="/dados/teste", namespace="/oper/dados/teste", automount="auto.grupo" , rede=rede, grupo_trabalho=grupo_trabalho).save()
    mixer.blend(StorageGrupoAcessoMontagem, ip='192.168.0.1', parametro='-fstype=nfs4,rw', tipo='OPERACIONAL', montagem="/scripts/teste", namespace="/oper/scripts/teste", automount="auto.grupo", rede=rede, grupo_trabalho=grupo_trabalho).save()
    mixer.blend(StorageGrupoAcessoMontagem, ip='192.168.0.1', parametro='-fstype=nfs4,rw', tipo='OPERACIONAL', montagem="/log/teste", namespace="/oper/log/teste", automount="auto.grupo", rede=rede, grupo_trabalho=grupo_trabalho).save()
    mixer.blend(StorageGrupoAcessoMontagem, ip='192.168.0.5', parametro='-fstype=nfs4,rw', tipo='OPERACIONAL', montagem="/share/teste", namespace="/share/teste", automount="auto.grupo", rede=rede, grupo_trabalho=grupo_trabalho).save()
    mixer.blend(StorageGrupoAcessoMontagem, ip='192.168.0.2', parametro='-fstype=nfs4,ro', tipo='OPERACIONAL', montagem="/oper", namespace="/oper", automount="auto.oper", rede=rede).save()
    mixer.blend(StorageGrupoAcessoMontagem, ip='192.168.0.6', parametro='-fstype=nfs4,ro', tipo='OPERACIONAL', montagem="/oper/share", namespace="/share", automount="auto.oper", rede=rede).save()
    mixer.blend(StorageGrupoAcessoMontagem, ip='192.168.0.10', parametro='-fstype=nfs4,rw', tipo='OPERACIONAL', montagem="*", namespace="/HOME/&", automount="auto.home",rede=rede).save()

    responsavel_grupo_trabalho = mixer.blend(ResponsavelGrupoTrabalho, grupo=grupo_trabalho, responsavel=responsavel_grupo)
    responsavel_grupo_trabalho.save()
    grupo_trabalho.gid = 9000
    grupo_trabalho.desenvolvimento = True
    grupo_trabalho.operacional = True
    grupo_trabalho.save_confirm()

    hostnameip = mixer.blend(HostnameIP, hostname='server1', ip='192.168.0.2', tipo=rede)
    hostnameip.save()

    servidor = mixer.blend(Servidor, nome='server1', descricao="Servidor de TESTE")
    servidor.save()
    servidor_host = mixer.blend(ServidorHostnameIP, servidor=servidor, hostnameip=hostnameip)
    servidor_host.save()

    request = RequestFactory().get(reverse("infra:criar_servidor_ldap", kwargs={"pk": servidor.pk}))
    request = message_middleware(request)
    request.user = superuser

    freeipa = FreeIPA(request) 
    freeipa.set_grupo(grupo_trabalho)
    history_core = HistoryCore(request)
    history_core.update_grupo_acesso(grupo=grupo_trabalho, assunto="Nova conta de Grupo de Trabalho")
    UpdateGrupoAcesso(client_feeipa=freeipa, history_core=history_core).update_acesso(grupo_trabalho)

    grupo_acesso_dev = GrupoAcesso.objects.filter(grupo_trabalho__id=grupo_trabalho.id, tipo='DESENVOLVIMENTO')
    assert grupo_acesso_dev.exists() == True
    equipamento_grupo_acesso = mixer.blend(EquipamentoGrupoAcesso, equipamento=servidor.equipamento_ptr, grupo_acesso=grupo_acesso_dev[0])
    equipamento_grupo_acesso.save()

    grupo_acesso_oper = GrupoAcesso.objects.filter(grupo_trabalho__id=grupo_trabalho.id, tipo='OPERACIONAL')
    assert grupo_acesso_oper.exists() == True
    equipamento_grupo_acesso = mixer.blend(EquipamentoGrupoAcesso, equipamento=servidor.equipamento_ptr, grupo_acesso=grupo_acesso_oper[0])
    equipamento_grupo_acesso.save()

    response = CriarServidorLdapView.as_view()(request, pk=servidor.pk)
    assert response.status_code == 302

    assert freeipa.host_find_count(fqdn=servidor.freeipa_name) == 1
    assert freeipa.automountlocation_find_count(cn=servidor.freeipa_name_mount) == 1
    assert freeipa.automountmap_find_count(automountlocationcn=servidor.freeipa_name_mount, automountmapname=grupo_acesso_oper[0].automountmap) == 1
    assert freeipa.automountkey_find_count(automountlocationcn=servidor.freeipa_name_mount, automountmapautomountmapname=grupo_acesso_oper[0].automountmap) == 4
    assert freeipa.automountkey_find_count(automountlocationcn=servidor.freeipa_name_mount, automountmapautomountmapname='auto.oper') == 2
    assert freeipa.automountkey_find_count(automountlocationcn=servidor.freeipa_name_mount, automountmapautomountmapname='auto.home') == 1
    assert freeipa.hbacrule_show(cn=grupo_acesso_oper[0].hbac_freeipa)['result']['memberhost_host'] == ['server1.cptec.inpe.br']

    grupos_acesso = GrupoAcesso.objects.filter(grupo_trabalho__id=grupo_trabalho.pk)
    for grupoacesso  in grupos_acesso: 
        assert freeipa.hbacrule_delete(grupoacesso.hbac_freeipa)
    assert freeipa.remove_grupo(grupo_trabalho) == True
    assert freeipa.host_delete(servidor.freeipa_name) == True
    assert freeipa.automountlocation_del(servidor.freeipa_name_mount) == True
    assert HostnameIP.objects.get(pk=hostnameip.pk).reservado == False





















