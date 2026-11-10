from apps.core.models import GrupoAcesso, OperatingSystem, ServidorOperatingSystem, ServidorTenants, Tenants
from apps.infra.utils.xen_crud import XenCrud
from secrets import choice
from types import SimpleNamespace
from requests.exceptions import RequestException
from python_freeipa.exceptions import FreeIPAError
from XenAPI import Failure as XenFailure
from urllib.parse import urlencode

from django.contrib import admin, messages
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.urls import path, reverse
from django.template.response import TemplateResponse
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from apps.core.utils.freeipa import FreeIPA
from apps.core.tasks import send_email_task
from apps.infra.forms import (AmbienteVirtualServidorInLineForm,
                              EquipamentoGrupoAcessoForm, EquipamentoParteForm,
                              HostnameIPForm, HostnameIPInLineForm, OcorrenciaChecklistInLineForm,
                              OcorrenciaInLineForm, ServidorForm, ServidorOperatingSystemInLineForm, TemplateComandoInLineForm,
                              StorageAreaGrupoTrabalhoInLineForm, ServidorTenantsInLineForm)
from apps.infra.models import (AmbienteVirtual, NetBoxServerOperations,
                               Equipamento, EquipamentoGrupoAcesso, EquipamentoParte,
                               HostnameIP, Ocorrencia, Rede, Servidor,
                               ServidorHostnameIP, ServidorNagiosServico, Storage, StorageArea,
                               StorageAreaGrupoTrabalho, Supercomputador, TemplateComando, TemplateHostnameIP, TemplateVM)
from apps.infra.utils.freeipa_location import Automount
from apps.infra.utils.history import HistoryInfra
from apps.infra.services.netbox_storage import get_storage_detail, get_storage_inventory
from apps.infra.services.netbox_server import get_server_detail, get_server_inventory
from apps.infra.utils.netbox import get_ip_addresses, get_prefixes
from apps.infra.forms import NetBoxServidorForm
from apps.infra.services.server_registration import PHYSICAL, VIRTUAL, NetBoxError, search_servers, get_server_snapshot, update_server_inventory
from apps.infra.services.netbox_vm import load_vm_target
from apps.monitoramento.models.nagios import NagiosServicos
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html


def netbox_operational_host(device_id, kind=PHYSICAL):
    snapshot = get_server_snapshot(kind, device_id)
    addresses = [(item['hostname'], item['ip']) for item in snapshot['netbox_ips']]
    if not addresses:
        raise OSError('Cadastre um IP no NetBox antes de executar a operação.')
    hostname = addresses[0][0].rstrip('.')
    return SimpleNamespace(
        netbox_object_id=device_id, enderecos_operacionais=addresses,
        freeipa_name=hostname if '.' in hostname else f'{hostname}.cptec.inpe.br',
        freeipa_name_mount=f"mount_{snapshot['nome']}",
    ), snapshot


def virtual_server_detail(device_id):
    snapshot = get_server_snapshot(VIRTUAL, device_id)
    return {
        'name': snapshot['nome'], 'model': snapshot['modelo'], 'asset_tag': snapshot['patrimonio'],
        'serial': snapshot['serie'], 'description': snapshot['descricao'], 'comments': snapshot.get('comments', ''),
        'site': snapshot['netbox_localizacao'], 'rack': '—', 'status': '—',
        'primary_ip': snapshot['netbox_ips'][0]['ip'] if snapshot['netbox_ips'] else '—',
    }


def log_netbox_operation(request, operation, name, message):
    LogEntry.objects.create(
        user_id=request.user.pk,
        content_type=ContentType.objects.get_for_model(operation),
        object_id=str(operation.pk), object_repr=name[:200],
        action_flag=CHANGE, change_message=message,
    )

class OcorrenciaInLine(admin.TabularInline):
    model = Ocorrencia
    fields = ["ocorrencia", "descricao", "status", "data"]
    extra = 0
    form = OcorrenciaInLineForm

    def get_readonly_fields(self, request, obj=None):
        fields = []
        fields.append("data")
        return fields

    def has_add_permission(self, request, obj=None):
        return False


class TemplateComandoInLine(admin.TabularInline):
    model = TemplateComando
    fields = ("comando", "configuracao","prioridade")
    extra = 0
    form = TemplateComandoInLineForm


class StorageAreaGrupoTrabalhoInLine(admin.TabularInline):
    model = StorageAreaGrupoTrabalho
    fields = ("storage_area", "quota")
    extra = 0
    form = StorageAreaGrupoTrabalhoInLineForm


class StorageAreaInLine(admin.TabularInline):
    model = StorageArea
    fields = ("area", "tipo","capacidade")
    extra = 0


class GrupoAcessoEquipamentoInLine(admin.TabularInline):
    model = EquipamentoGrupoAcesso
    extra = 0
    verbose_name = "Grupo de Acesso"
    verbose_name_plural = "Grupos de Acesso"
    form = EquipamentoGrupoAcessoForm

    def has_change_permission(self, request, obj=None):
        return False
    
    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        field = super(GrupoAcessoEquipamentoInLine, self).formfield_for_foreignkey(db_field, request, **kwargs)
        # field.queryset = field.queryset.filter(grupo_acesso__contains=request._obj_.tipo_uso).exclude(equipamento__id=request._obj_.id)
        return field


class GrupoAcessoEquipamentoInLineRead(admin.TabularInline):
    model = EquipamentoGrupoAcesso
    fields = ["equipamento_name","equipamento_descricao","equipamento_tipo"]
    readonly_fields = ["equipamento_name","equipamento_descricao","equipamento_tipo"]
    verbose_name = "Equipamento"
    verbose_name_plural = "Equipamentos"
    extra = 0

    def equipamento_name(self, obj):
        return obj.equipamento.nome()
    equipamento_name.short_description = "Equipamento"
    
    def equipamento_descricao(self, obj):
        return obj.equipamento.descricao
    equipamento_descricao.short_description = "Descrição"

    def equipamento_tipo(self, obj):
        return obj.equipamento.tipo
    equipamento_tipo.short_description = "Tipo"

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


class HostnameIPServidorInLine(admin.TabularInline):
    model = ServidorHostnameIP
    extra = 0
    form = HostnameIPInLineForm
    
    def has_change_permission(self, request, obj=None):
        return False


class HostnameIPTemplateInLine(admin.TabularInline):
    model = TemplateHostnameIP
    extra = 0
    form = HostnameIPInLineForm
    
    def has_change_permission(self, request, obj=None):
        return False


class AmbienteVirtualServidorInLine(admin.TabularInline):
    model = AmbienteVirtual.servidor.through
    fields = ("servidor",)
    extra = 0
    verbose_name = "Servidor Físico"
    verbose_name_plural = "Servidores Físicos"
    form = AmbienteVirtualServidorInLineForm


class ServicoNagiosInLine(admin.TabularInline):
    model = ServidorNagiosServico
    extra = 0
    verbose_name = "Nagios Serviço"
    verbose_name_plural = "Nagios Serviços"

    def get_formset(self, request, obj=None, **kwargs):
        formset = super(ServicoNagiosInLine, self).get_formset(request, obj, **kwargs)
        formset.form.base_fields["nagios_servico"].label = "Serviço"
        return formset


class TenantsInLine(admin.TabularInline):
    model = ServidorTenants
    fields = ("tenant",)
    extra = 0
    form = ServidorTenantsInLineForm

    def get_formset(self, request, obj=None, **kwargs):
        formset = super(TenantsInLine, self).get_formset(request, obj, **kwargs)
        return formset

class OperatingSystemInLine(admin.TabularInline):
    model = ServidorOperatingSystem
    fields = ("so",)
    extra = 0
    form = ServidorOperatingSystemInLineForm

    def get_formset(self, request, obj=None, **kwargs):
        formset = super(OperatingSystemInLine, self).get_formset(request, obj, **kwargs)
        return formset

class OcorrenciaChecklistInLine(admin.TabularInline):
    model = Ocorrencia
    fields = ("equipamento","descricao")
    extra = 0
    verbose_name = "Ocorrência de Equipamento"
    verbose_name_plural =  "Ocorrências de Equipamento"
    form = OcorrenciaChecklistInLineForm

@admin.register(HostnameIP)
class HostnameIPAdmin(admin.ModelAdmin):
    change_form_template = "infra/admin/change_form_hostnameip.html"
    search_fields = ["hostname", "ip"]
    list_display = ("hostname", "ip", "reservado")
    form = HostnameIPForm

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        records = get_ip_addresses()
        query = request.GET.get("q", "").strip()
        rows = [{"name": item.get("dns_name") or "—", "address": item.get("address") or "—",
                 "status": (item.get("status") or {}).get("label") or "—",
                 "description": item.get("description") or "—"} for item in (records or [])]
        if query:
            rows = [row for row in rows if query.casefold() in row["name"].casefold() or query.casefold() in row["address"].casefold()]
        context = {**self.admin_site.each_context(request), "title": "Hostnames e IPs", "opts": self.model._meta,
                   "rows": rows, "query": query, "netbox_error": records is None,
                   "columns": ("Hostname", "Endereço IP", "Status", "Descrição")}
        return TemplateResponse(request, "infra/admin/netbox_ipam_list.html", context, status=502 if records is None else 200)


@admin.register(Supercomputador)
class SupercomputadorAdmin(admin.ModelAdmin):
    search_fields = ["marca", "modelo"]
    list_display = ("marca", "modelo", "kafka_topico_realtime", "kafka_topico_historico",)
    exclude = ("consumo", "grupos_acesso", "patrimonio", "serie", "descricao", "tipo_uso", "tipo", "status", "grupos",)
    inlines = (OcorrenciaInLine,)


@admin.register(Storage)
class StorageAdmin(admin.ModelAdmin):
    search_fields = ["marca", "modelo"]
    readonly_fields = ("atualizacao",)
    list_display = ("marca", "modelo", "descricao", "capacidade",)
    exclude = ("consumo", "grupos_acesso", "patrimonio", "serie",  "tipo_uso", "tipo", "status", "grupos",)
    inlines = (StorageAreaInLine, OcorrenciaInLine)

    def get_urls(self):
        return [
            path("netbox/<int:device_id>/", self.admin_site.admin_view(self.netbox_detail_view), name="infra_storage_netbox_detail"),
        ] + super().get_urls()

    def netbox_detail_view(self, request, device_id):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        device = get_storage_detail(device_id)
        if device == {}:
            raise Http404("Dispositivo não é um storage ou controladora")
        if device is None:
            return JsonResponse({"error": "Não foi possível consultar o NetBox."}, status=502)
        return JsonResponse({"device": device})

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        inventory = get_storage_inventory()
        search_query = request.GET.get("q", "").strip()
        selected_role = request.GET.get("role", "")
        if selected_role not in {"controller", "storage"}:
            selected_role = ""
        filtered_inventory = [device for device in (inventory or [])
                              if (not selected_role or device["role_key"] == selected_role
                                  or (selected_role == "storage" and device["role_key"] == "disk-array"))
                              and (not search_query or search_query.casefold() in device["name"].casefold())]
        context = {
            **self.admin_site.each_context(request),
            "title": "Storages | controllers",
            "opts": self.model._meta,
            "inventory": filtered_inventory,
            "netbox_error": inventory is None,
            "search_query": search_query,
            "selected_role": selected_role,
        }
        return TemplateResponse(request, "infra/admin/netbox_storage_list.html", context, status=502 if inventory is None else 200)

class TenantsFilter(admin.SimpleListFilter):
    title = _('Tenant')
    parameter_name = 'tenants'

    def lookups(self, request, model_admin):
        tenants = Tenants.objects.all()
        return [(tenant.id, tenant.tenants) for tenant in tenants]

    def queryset(self, request, queryset):
        try:
            queryt = ServidorTenants.objects.all()
            if self.value():
                tenants = queryt.filter(tenant_id=self.value())
                tenants_id = [t.servidor_id for t in tenants]
                return queryset.filter(id__in=tenants_id)
        except Exception as err:
            print(f'ERROR FILTER TENANTS: {err}')
        return queryset


class OperatingSystemFilter(admin.SimpleListFilter):
    title = _('SO')
    parameter_name = 'so'

    def lookups(self, request, model_admin):
        operating_systems = OperatingSystem.objects.all()
        return [(so.id, so.so) for so in operating_systems]

    def queryset(self, request, queryset):
        try:
            queryop = ServidorOperatingSystem.objects.all()
            if self.value():
                server = queryop.filter(so_id=self.value())
                servidor_ids = [s.servidor_id for s in server]
                return queryset.filter(id__in=servidor_ids)
        except Exception as err:
            print(f'ERROR FILTER SO: {err}')
        return queryset

@admin.register(Servidor)
class ServidorAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    change_form_template = "infra/admin/change_form_servidor_netbox.html"
    delete_confirmation_template = "infra/admin/delete_confirmation_servidor.html"
    change_list_template  = "infra/admin/change_list_servidor.html"
    search_fields = ["nome", "patrimonio", "marca", "modelo", "descricao", "servicos", "grupos"]
    list_filter = [
        "tipo_uso", 
        "tipo", 
        "datacenter",
        TenantsFilter,
        OperatingSystemFilter
    ]
    list_display = ("nome", "tipo", "tipo_uso",  "datacenter",  "descricao", "grupo", "responsavel", "status")
    fields = ["nome", "tipo", "tipo_uso", "datacenter", "descricao", "marca", "modelo", "serie", "patrimonio", "garantia", "consumo", "vinculado", "status", "conta", 'vm_remover']
    readonly_fields = ("status","conta")
    form = NetBoxServidorForm
    inlines = [HostnameIPServidorInLine,]

    def get_urls(self):
        return [
            path("netbox/buscar/", self.admin_site.admin_view(self.netbox_search_view), name="infra_servidor_netbox_search"),
            path("netbox/vms/", self.admin_site.admin_view(self.netbox_vm_list_view), name="infra_servidor_netbox_vms"),
            path("netbox/vms/<int:device_id>/operacional/", self.admin_site.admin_view(self.netbox_operational_view), {'kind': VIRTUAL}, name="infra_servidor_netbox_vm_operational"),
            path("netbox/vms/<int:device_id>/historico/", self.admin_site.admin_view(self.netbox_history_view), {'kind': VIRTUAL}, name="infra_servidor_netbox_vm_history"),
            path("netbox/vms/<int:device_id>/", self.admin_site.admin_view(self.netbox_detail_view), {'kind': VIRTUAL}, name="infra_servidor_netbox_vm_detail"),
            path("netbox/<int:device_id>/operacional/", self.admin_site.admin_view(self.netbox_operational_view), name="infra_servidor_netbox_operational"),
            path("netbox/<int:device_id>/historico/", self.admin_site.admin_view(self.netbox_history_view), name="infra_servidor_netbox_history"),
            path("operacionais/", self.admin_site.admin_view(self.operational_changelist_view), name="infra_servidor_operacionais"),
            path("netbox/<int:device_id>/", self.admin_site.admin_view(self.netbox_detail_view), name="infra_servidor_netbox_detail"),
        ] + super().get_urls()

    def netbox_vm_list_view(self, request):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        try:
            offset = int(request.GET.get('offset', '0'))
            if offset < 0 or offset > 1000000:
                raise ValueError
            query = request.GET.get('q', '').strip()
            if len(query) > 200:
                raise ValueError
            page = search_servers(VIRTUAL, query, offset)
        except ValueError:
            return JsonResponse({'error': 'Busca inválida.'}, status=400)
        except NetBoxError as error:
            return JsonResponse({'error': str(error)}, status=error.status)
        return TemplateResponse(request, 'infra/admin/netbox_vm_list.html', {
            **self.admin_site.each_context(request), 'title': 'Máquinas virtuais',
            'vms': page['results'], 'more': page['more'], 'offset': offset, 'query': query,
        })

    def netbox_history_view(self, request, device_id, kind=PHYSICAL):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        operation = NetBoxServerOperations.objects.filter(netbox_object_type=kind, netbox_object_id=device_id).first()
        legacy = Servidor.objects.filter(netbox_object_type=kind, netbox_object_id=device_id).first()
        entries = []
        for item in (operation, legacy):
            if item:
                entries.extend(LogEntry.objects.filter(content_type=ContentType.objects.get_for_model(item), object_id=str(item.pk)))
        entries.sort(key=lambda entry: entry.action_time, reverse=True)
        return TemplateResponse(request, 'infra/admin/netbox_server_history.html', {
            **self.admin_site.each_context(request), 'title': 'Histórico do servidor',
            'entries': entries, 'device_id': device_id, 'is_vm': kind == VIRTUAL,
        })

    def netbox_operational_view(self, request, device_id, kind=PHYSICAL):
        if request.method not in ('GET', 'POST'):
            return JsonResponse({'error': 'Método não permitido.'}, status=405)
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        try:
            device = get_server_detail(device_id) if kind == PHYSICAL else virtual_server_detail(device_id)
        except NetBoxError as error:
            return JsonResponse({'error': str(error)}, status=error.status)
        if device == {}:
            raise Http404('Dispositivo não é um servidor')
        if device is None:
            return JsonResponse({'error': 'Não foi possível consultar o NetBox.'}, status=502)
        if request.method == 'POST':
            if not self.has_change_permission(request):
                raise PermissionDenied
            action = request.POST.get('action', 'save')
            if action == 'delete_vm':
                operation = NetBoxServerOperations.objects.filter(netbox_object_type=kind, netbox_object_id=device_id).first()
                if kind != VIRTUAL or not operation or not operation.vm_remover or not operation.vm_ambiente_virtual_id:
                    return JsonResponse({'error': 'Não há VM provisionada para remover.'}, status=400)
                try:
                    target = load_vm_target(device_id)
                    task = XenCrud(request, target, operation.vm_ambiente_virtual).delete_vm()
                except (NetBoxError, XenFailure, OSError, RequestException) as error:
                    return JsonResponse({'error': str(error)}, status=502)
                if not task:
                    return JsonResponse({'error': 'A remoção não foi enviada para execução.'}, status=502)
                log_netbox_operation(request, operation, device['name'], 'Remoção de VM iniciada')
                from django.shortcuts import redirect
                return redirect(f'{request.path}?{urlencode({"task_id": task.id})}')
            if action == 'create_vm':
                if kind != VIRTUAL:
                    return JsonResponse({'error': 'Esta ação exige uma VM.'}, status=400)
                operation = NetBoxServerOperations.objects.filter(netbox_object_type=kind, netbox_object_id=device_id).first()
                template_id = request.POST.get('template', '')
                cpu = request.POST.get('cpu', '')
                memory = request.POST.get('memoria', '')
                if not operation or operation.conta == 'Aguardando' or not template_id.isdecimal() or cpu not in ('1', '2', '4', '8') or memory not in ('2', '4', '8', '16'):
                    return JsonResponse({'error': 'Dados de criação da VM inválidos.'}, status=400)
                template = TemplateVM.objects.filter(pk=template_id).first()
                if not template:
                    return JsonResponse({'error': 'Template não encontrado.'}, status=400)
                try:
                    target = load_vm_target(device_id)
                    task = XenCrud(request, target, template.ambiente_virtual).create_vm(template, memory, cpu)
                except (NetBoxError, XenFailure, OSError, RequestException) as error:
                    return JsonResponse({'error': str(error)}, status=502)
                if not task:
                    return JsonResponse({'error': 'A VM não foi enviada para criação.'}, status=400)
                log_netbox_operation(request, operation, device['name'], 'Criação de VM iniciada')
                from django.shortcuts import redirect
                return redirect(f'{request.path}?{urlencode({"task_id": task.id})}')
            if action in ('update_occurrence', 'delete_occurrence'):
                status = request.POST.get('status', '')
                occurrence_id = request.POST.get('occurrence', '')
                if not occurrence_id.isdecimal() or (action == 'update_occurrence' and status not in ('Analisando', 'Aberto', 'Fechado', 'Suspenso')):
                    return JsonResponse({'error': 'Ocorrência inválida.'}, status=400)
                occurrence = Ocorrencia.objects.filter(netbox_object_type=kind, netbox_object_id=device_id,
                    pk=occurrence_id).first()
                if not occurrence:
                    raise Http404('Ocorrência não encontrada')
                if action == 'delete_occurrence':
                    occurrence.delete()
                else:
                    occurrence.status = status
                    occurrence.save(update_fields=['status', 'data'])
                from django.shortcuts import redirect
                return redirect(request.path)
            if action == 'create_freeipa':
                operation = NetBoxServerOperations.objects.filter(netbox_object_type=kind, netbox_object_id=device_id).first()
                if not operation or not operation.grupos_acesso.exists() or operation.conta != 'Aguardando':
                    return JsonResponse({'error': 'Adicione um grupo de acesso e confira o estado da conta.'}, status=400)
                try:
                    host, snapshot = netbox_operational_host(device_id, kind)
                    client = FreeIPA(request)
                    if not client.set_host(host, description=snapshot['descricao']):
                        return JsonResponse({'error': 'O FreeIPA não criou o servidor.'}, status=502)
                    automount = Automount(client, host, request)
                    automount.adicionar_grupos(operation.grupos_acesso.all())
                    automount.adicionar_oper()
                    automount.adicionar_home()
                except (NetBoxError, FreeIPAError, RequestException, OSError, KeyError, ValueError) as error:
                    return JsonResponse({'error': str(error)}, status=502)
                operation.conta = 'FreeIPA'
                operation.save(update_fields=['conta'])
                log_netbox_operation(request, operation, device['name'], 'Servidor criado no FreeIPA')
                send_email_task.delay('Servidor Criado', f"O Servidor: {device['name']} foi criado no FreeIPA, por: {request.user.username}", [settings.EMAIL_SYSADMIN])
                from django.shortcuts import redirect
                return redirect(request.path)
            if action == 'create_local':
                operation = NetBoxServerOperations.objects.filter(netbox_object_type=kind, netbox_object_id=device_id).first()
                if not operation or not operation.grupos_acesso.exists() or operation.conta != 'Aguardando':
                    return JsonResponse({'error': 'Adicione um grupo de acesso e confira o estado da conta.'}, status=400)
                operation.conta = 'Local'
                operation.save(update_fields=['conta'])
                log_netbox_operation(request, operation, device['name'], 'Conta local criada')
                send_email_task.delay('Servidor Criado', f"O Servidor: {device['name']} foi criado com conta Local, por: {request.user.username}", [settings.EMAIL_SYSADMIN])
                from django.shortcuts import redirect
                return redirect(request.path)
            if action == 'toggle_status':
                operation, _ = NetBoxServerOperations.objects.get_or_create(netbox_object_type=kind, netbox_object_id=device_id)
                operation.status = 'Em uso' if operation.status == 'Manutenção' else 'Manutenção'
                operation.save(update_fields=['status'])
                if operation.status == 'Em uso':
                    operation.nagios_servicos.add(*NagiosServicos.objects.filter(padrao=True))
                log_netbox_operation(request, operation, device['name'], f'Status operacional alterado para {operation.status}')
                send_email_task.delay('Mudança de Status do Servidor',
                    f"O Servidor: {device['name']} teve seu status alterado para: {operation.status} por: {request.user.username}",
                    [settings.EMAIL_SYSADMIN, settings.EMAIL_SUPORTE])
                from django.shortcuts import redirect
                return redirect(request.path)
            if action == 'add_occurrence':
                title = request.POST.get('ocorrencia', '').strip()
                description = request.POST.get('descricao', '').strip()
                status = request.POST.get('status', '')
                if not title or len(title) > 255 or len(description) > 255 or status not in ('Analisando', 'Aberto', 'Fechado', 'Suspenso'):
                    return JsonResponse({'error': 'Ocorrência inválida.'}, status=400)
                Ocorrencia.objects.create(ocorrencia=title, descricao=description, status=status,
                    netbox_object_type=kind, netbox_object_id=device_id, equipamento_nome=device['name'])
                from django.shortcuts import redirect
                return redirect(request.path)
            if action == 'update_inventory':
                values = {field: request.POST[field].strip() for field in ('nome', 'serie', 'patrimonio', 'descricao', 'comentarios') if field in request.POST}
                if not values or any(len(value) > (10000 if field == 'comentarios' else 255) for field, value in values.items()) or not values.get('nome', device['name']):
                    return JsonResponse({'error': 'Dados de inventário inválidos.'}, status=400)
                try:
                    update_server_inventory(kind, device_id, values)
                except NetBoxError as error:
                    return JsonResponse({'error': str(error)}, status=error.status if error.status >= 400 else 502)
                from django.shortcuts import redirect
                return redirect(request.path)
            if action in ('add_group', 'remove_group', 'add_nagios', 'remove_nagios'):
                group_action = action.endswith('group')
                model = GrupoAcesso if group_action else NagiosServicos
                field = 'group' if group_action else 'service'
                try:
                    target = model.objects.get(pk=request.POST.get(field))
                except (model.DoesNotExist, ValueError, TypeError):
                    return JsonResponse({'error': 'Seleção inválida.'}, status=400)
                operation, _ = NetBoxServerOperations.objects.get_or_create(netbox_object_type=kind, netbox_object_id=device_id)
                relation = operation.grupos_acesso if group_action else operation.nagios_servicos
                if group_action and operation.conta == 'FreeIPA' and not (relation.filter(pk=target.pk).exists() == action.startswith('add_')):
                    try:
                        host, _ = netbox_operational_host(device_id, kind)
                        automount = Automount(FreeIPA(request), host, request)
                        if action == 'add_group':
                            automount.adicionar_grupos([target])
                        else:
                            automount.remover_grupos([target])
                    except (NetBoxError, FreeIPAError, RequestException, OSError, KeyError, ValueError) as error:
                        return JsonResponse({'error': str(error)}, status=502)
                if action.startswith('add_'):
                    relation.add(target)
                else:
                    relation.remove(target)
                from django.shortcuts import redirect
                return redirect(request.path)
            if action != 'save':
                return JsonResponse({'error': 'Ação inválida.'}, status=400)
            tipo_uso = request.POST.get('tipo_uso', '')
            if tipo_uso not in dict(Equipamento.TIPOS_USO):
                return JsonResponse({'error': 'Tipo de uso inválido.'}, status=400)
            operation, _ = NetBoxServerOperations.objects.get_or_create(netbox_object_type=kind, netbox_object_id=device_id)
            operation.tipo_uso = tipo_uso
            operation.save(update_fields=['tipo_uso'])
            from django.shortcuts import redirect
            return redirect(request.path)
        return TemplateResponse(request, 'infra/admin/netbox_server_operations.html', {
            **self.admin_site.each_context(request),
            'title': device['name'], 'device': device, 'device_id': device_id,
            'is_vm': kind == VIRTUAL,
            'vm_templates': TemplateVM.objects.all() if kind == VIRTUAL else (),
            'task_status_url': reverse('celery_progress:task_status', args=[request.GET['task_id']]) if kind == VIRTUAL and request.GET.get('task_id', '').isascii() and 0 < len(request.GET.get('task_id', '')) <= 100 else '',
            'opts': self.model._meta,
            'operation': NetBoxServerOperations.objects.filter(netbox_object_type=kind, netbox_object_id=device_id).first(),
            'tipos_uso': Equipamento.TIPOS_USO,
            'occurrence_statuses': ('Analisando', 'Aberto', 'Fechado', 'Suspenso'),
            'groups': GrupoAcesso.objects.all(), 'nagios_services': NagiosServicos.objects.all(),
            'occurrences': Ocorrencia.objects.filter(
                Q(netbox_object_type=kind, netbox_object_id=device_id) |
                Q(equipamento_id__in=Servidor.objects.filter(netbox_object_type=kind, netbox_object_id=device_id).values('equipamento_ptr_id'))
            ).distinct(),
        })

    def netbox_search_view(self, request):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        if request.method != "GET":
            response = JsonResponse({"error": "Método não permitido."}, status=405)
            response["Allow"] = "GET"
            return response
        try:
            offset = int(request.GET.get("offset", "0"))
            query = request.GET.get("q", "").strip()
            if offset < 0 or offset > 1000000 or len(query) > 200:
                raise ValueError
        except ValueError:
            return JsonResponse({"error": "Busca ou página inválida."}, status=400)
        try:
            result = search_servers(request.GET.get("object_type", PHYSICAL), query, offset)
        except NetBoxError as error:
            return JsonResponse({"error": str(error)}, status=error.status)
        response = JsonResponse(result)
        response["Cache-Control"] = "no-store"
        return response

    def operational_changelist_view(self, request):
        response = super().changelist_view(request)
        if isinstance(response, TemplateResponse):
            response.template_name = "infra/admin/operational_server_list.html"
        return response

    def get_fields(self, request, obj=None):
        return ("netbox_tipo", "netbox_device", "atualizar_netbox", "tipo_uso", "servicos", "vinculado", "nome", "tipo", "marca", "modelo", "serie", "patrimonio", "descricao", "netbox_localizacao", "ips_netbox", "netbox_atualizado_em", "status", "conta") + (("vm_remover",) if obj and obj.tipo == "Servidor Virtual" and obj.vm_ambiente_virtual_id else ())

    def get_readonly_fields(self, request, obj=None):
        fields = ("tipo", "marca", "modelo", "netbox_localizacao", "ips_netbox", "netbox_atualizado_em", "status", "conta")
        if obj and not obj.netbox_object_id:
            fields += ("nome", "serie", "patrimonio", "descricao")
        if obj and not self.has_change_permission(request, obj):
            fields += ("netbox_tipo", "netbox_device", "atualizar_netbox")
        return fields

    @admin.display(description="Tipo no NetBox")
    def netbox_tipo(self, obj):
        return obj.tipo if obj.netbox_object_id else "Registro antigo"

    @admin.display(description="Servidor (NetBox)")
    def netbox_device(self, obj):
        return f"{obj.nome} (ID {obj.netbox_object_id})" if obj.netbox_object_id else obj.nome

    @admin.display(description="Atualização do NetBox")
    def atualizar_netbox(self, obj):
        return obj.netbox_atualizado_em or "—"

    def get_inlines(self, request, obj=None):
        if obj is None:
            return ()
        operational = (GrupoAcessoEquipamentoInLine, OcorrenciaInLine, ServicoNagiosInLine, TenantsInLine, OperatingSystemInLine)
        return operational if obj.netbox_object_id else (HostnameIPServidorInLine,) + operational

    @admin.display(description="IPs obtidos do NetBox")
    def ips_netbox(self, obj):
        return " | ".join(f"{name}: {address}" for name, address in obj.enderecos_operacionais) if obj and obj.netbox_object_id else "—"

    def netbox_detail_view(self, request, device_id, kind=PHYSICAL):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        try:
            device = get_server_detail(device_id) if kind == PHYSICAL else virtual_server_detail(device_id)
        except NetBoxError as error:
            return JsonResponse({'error': str(error)}, status=error.status)
        if device == {}:
            raise Http404("Dispositivo não é um servidor")
        if device is None:
            return JsonResponse({"error": "Não foi possível consultar os dados."}, status=502)
        return JsonResponse({"device": device})

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        search_query = request.GET.get("netbox_q", "").strip()
        asset_tag_query = request.GET.get("netbox_asset_tag", "").strip()
        try:
            offset = max(0, int(request.GET.get("netbox_offset", "0")))
        except ValueError:
            offset = 0
        inventory = get_server_inventory(limit=15, offset=offset, search=search_query, asset_tag=asset_tag_query)
        if inventory:
            local_ids = dict(Servidor.objects.filter(netbox_object_type=PHYSICAL, netbox_object_id__in=[item["id"] for item in inventory["devices"]]).values_list("netbox_object_id", "pk"))
            for item in inventory["devices"]:
                local_id = local_ids.get(item["id"])
                item["portal_url"] = reverse("admin:infra_servidor_netbox_operational", args=[item['id']])
                item["detail_url"] = reverse("admin:infra_servidor_netbox_detail", args=[item['id']])
                item["has_operational_record"] = bool(local_id)
        context = {**self.admin_site.each_context(request), **(extra_context or {}),
                   "has_add_permission": self.has_add_permission(request), "has_change_permission": self.has_change_permission(request),
                   "title": "Servidores", "opts": self.model._meta,
                   "netbox_servers": inventory["devices"] if inventory else [],
                   "netbox_count": inventory["count"] if inventory else None,
                   "netbox_next_offset": inventory["next_offset"] if inventory else None,
                   "netbox_previous_offset": inventory["previous_offset"] if inventory else None,
                   "netbox_error": inventory is None, "netbox_search_query": search_query,
                   "netbox_asset_tag_query": asset_tag_query}
        return TemplateResponse(request, self.change_list_template, context,
                                status=502 if inventory is None else 200)
    
    #Listar os grupos um em cada linha
    def grupo(self, obj):
        grupos = obj.grupo_acesso_name().split(" | ")
        if not grupos:
            return "-"
        
        primeiro_grupo = grupos[0]
        grupos_extras = grupos[1:]
        
        html = format_html('<div>{}</div>', primeiro_grupo)
        for grupo in grupos_extras:
            html += format_html('<div style="margin-top: 0px;">{}</div>', grupo)
        
        return html
    grupo.short_description = "Grupo"

    # Coluna responsável
    def responsavel(self, obj):
        grupos_acesso = obj.grupos_acesso.all()
        if not grupos_acesso.exists():
            return "-"
        
        responsaveis_por_grupo = []
        
        for grupo_acesso in grupos_acesso:
            # Acessa o GrupoTrabalho relacionado
            grupo_trabalho = grupo_acesso.grupo_trabalho
            
            # Obtém todos os responsáveis desse grupo
            responsaveis = grupo_trabalho.responsavel.all()
            
            if responsaveis.exists():
                # Formata os nomes dos responsáveis
                nomes = [f"{resp.first_name} {resp.last_name}" for resp in responsaveis]
                responsaveis_por_grupo.append(
                    f"{', '.join(nomes)}"
                )
            else:
                responsaveis_por_grupo.append(
                    f"{grupo_trabalho.grupo}: Sem responsável definido"
                )
        
        return format_html("<br>".join(responsaveis_por_grupo))

    responsavel.short_description = "Responsável"
    responsavel.allow_tags = True

    def save_model(self, request, obj, form, change):
        # New registrations are operational references, not local inventory entries.
        if isinstance(form, NetBoxServidorForm):
            return super().save_model(request, obj, form, change)
        # Compatibility for callers still using the legacy form.
        hostname_str = obj.nome.split(" | ")
        obj.nome = hostname_str[0]
        hostname = HostnameIP.objects.get(hostname=obj.nome)
        if change:
            if "descricao" in form.changed_data and obj.conta == "FreeIPA":
                FreeIPA(request).host_mod(obj.freeipa_name, description=obj.descricao)
            super().save_model(request, obj, form, change)
        else:
            hostname.reservado = True
            hostname.save()
            super().save_model(request, obj, form, change)
            ServidorHostnameIP.objects.create(servidor=obj, hostnameip=hostname)

    def delete_model(self, request, obj):
        for server_hostnameip in ServidorHostnameIP.objects.filter(servidor__id=obj.pk):
            hostnameip = server_hostnameip.hostnameip
            hostnameip.reservado = False
            hostnameip.save()
            HistoryInfra(request).delete_servidor(servidor=obj, hostnameip=hostnameip)
        if obj.conta == "FreeIPA":
            client_feeipa = FreeIPA(request)
            client_feeipa.automountlocation_del(obj.freeipa_name_mount)
            client_feeipa.host_delete(obj.freeipa_name)
        if obj.vm_remover and obj.vm_ambiente_virtual:
            XenCrud(request, obj, obj.vm_ambiente_virtual).delete_vm()
        return super().delete_model(request, obj)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, EquipamentoGrupoAcesso) and formset.instance.conta == "FreeIPA":
                Automount(FreeIPA(request), formset.instance, request).adicionar_grupos([instance.grupo_acesso])
                messages.add_message(request, messages.WARNING, "Precisa reiniciar o serviço de AUTOFS no Servidor!")
            if isinstance(instance, ServidorHostnameIP):
                hostnameip = instance.hostnameip
                hostnameip.reservado = True
                hostnameip.save()
                instance.save
        for obj in formset.deleted_objects:
            if isinstance(obj, EquipamentoGrupoAcesso) and formset.instance.conta == "FreeIPA":
                Automount(FreeIPA(request), formset.instance, request).remover_grupos([obj.grupo_acesso])
                messages.add_message(request, messages.WARNING, "Precisa reiniciar o serviço de AUTOFS no Servidor!")
            if isinstance(obj, ServidorHostnameIP):
                hostnameip = obj.hostnameip
                hostnameip.reservado = False
                hostnameip.save()
        return super().save_formset(request, form, formset, change)

    def response_change(self, request, obj):
        obj.grupos = " | ".join([x.grupo_acesso.replace(" | OPERACIONAL", "").replace(" | DESENVOLVIMENTO", "").replace(" | PESQUISA", "") for x in obj.grupos_acesso.all()])
        obj.save()
        return super(ServidorAdmin, self).response_change(request, obj)

    def get_form(self, request, obj=None, **kwargs):
            request._obj_ = obj
            return super(ServidorAdmin, self).get_form(request, obj, **kwargs)


@admin.register(TemplateVM)
class TemplateVMAdmin(admin.ModelAdmin):
    change_form_template = "infra/admin/change_form_template.html"
    search_fields = ["nome", "ambiente_virtual"]
    list_filter = ["ambiente_virtual"]
    list_display = ["nome", "configuracao", "ambiente_virtual" ]
    fields = ["nome", "configuracao", "ambiente_virtual"]
    readonly_fields = []
    inlines = (HostnameIPTemplateInLine,TemplateComandoInLine)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, TemplateHostnameIP):
                hostnameip = instance.hostnameip
                hostnameip.reservado = True
                hostnameip.save()
                instance.save
        for obj in formset.deleted_objects:
            if isinstance(obj, TemplateHostnameIP):
                hostnameip = obj.hostnameip
                hostnameip.reservado = False
                hostnameip.save()
        return super().save_formset(request, form, formset, change)

    def delete_model(self, request, obj):
        for template_hostnameip in TemplateHostnameIP.objects.filter(id=obj.pk):
            hostnameip = template_hostnameip.hostnameip
            hostnameip.reservado = False
            hostnameip.save()
        return super().delete_model(request, obj)

    def add_view(self, request, form_url="", extra_context=None):
        self.readonly_fields = []
        return super().add_view(request, form_url=form_url, extra_context=extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        self.readonly_fields = ['ambiente_virtual']
        return super().change_view(request, object_id, form_url=form_url, extra_context=extra_context)


@admin.register(EquipamentoParte)
class EquipamentoParteAdmin(admin.ModelAdmin):
    search_fields = ["patrimonio", "marca", "modelo"]
    list_display = ("patrimonio", "marca", "modelo", "vinculado", "status")
    readonly_fields = ("status",)
    form = EquipamentoParteForm
    inlines = (OcorrenciaInLine,)


@admin.register(AmbienteVirtual)
class AmbienteVirtualAdmin(admin.ModelAdmin):
    search_fields = ["nome"]
    list_display = ["nome", "virtualizador", "versao", "status", "network"]
    fields = ["nome", "virtualizador", "versao", "status", "network"]
    inlines = (AmbienteVirtualServidorInLine,)


@admin.register(Rede)
class RedeAdmin(admin.ModelAdmin):
    search_fields = ["rede", "ip"]
    list_display = ("rede", "ip", "prioridade_montagem")

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        records = get_prefixes()
        query = request.GET.get("q", "").strip()
        rows = [{"name": item.get("description") or "—", "address": item.get("prefix") or "—",
                 "status": (item.get("status") or {}).get("label") or "—",
                 "description": ((item.get("scope") or item.get("site") or {}).get("name") or "—")}
                for item in (records or [])]
        if query:
            rows = [row for row in rows if query.casefold() in row["name"].casefold() or query.casefold() in row["address"].casefold()]
        context = {**self.admin_site.each_context(request), "title": "Redes", "opts": self.model._meta,
                   "rows": rows, "query": query, "netbox_error": records is None,
                   "columns": ("Descrição", "Prefixo", "Status", "Local")}
        return TemplateResponse(request, "infra/admin/netbox_ipam_list.html", context, status=502 if records is None else 200)


