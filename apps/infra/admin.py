from apps.core.models import OperatingSystem, ServidorOperatingSystem, ServidorTenants, Tenants
from apps.infra.utils.xen_crud import XenCrud
from secrets import choice

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.urls import path
from django.template.response import TemplateResponse
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from apps.core.utils.freeipa import FreeIPA
from apps.infra.forms import (AmbienteVirtualServidorInLineForm,
                              EquipamentoGrupoAcessoForm, EquipamentoParteForm,
                              HostnameIPForm, HostnameIPInLineForm, OcorrenciaChecklistInLineForm,
                              OcorrenciaInLineForm, ServidorForm, ServidorOperatingSystemInLineForm, TemplateComandoInLineForm,
                              StorageAreaGrupoTrabalhoInLineForm, ServidorTenantsInLineForm)
from apps.infra.models import (AmbienteVirtual, 
                               EquipamentoGrupoAcesso, EquipamentoParte,
                               HostnameIP, Ocorrencia, Rede, Servidor,
                               ServidorHostnameIP, ServidorNagiosServico, Storage, StorageArea,
                               StorageAreaGrupoTrabalho, Supercomputador, TemplateComando, TemplateHostnameIP, TemplateVM)
from apps.infra.utils.freeipa_location import Automount
from apps.infra.utils.history import HistoryInfra
from apps.infra.services.netbox_storage import get_storage_detail, get_storage_inventory
from apps.infra.services.netbox_server import get_server_detail, get_server_inventory
from apps.infra.utils.netbox import get_ip_addresses, get_prefixes
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html

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
    change_form_template = "infra/admin/change_form_servidor.html"
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
    form = ServidorForm 
    inlines = [HostnameIPServidorInLine,]

    def get_urls(self):
        return [
            path("netbox/<int:device_id>/", self.admin_site.admin_view(self.netbox_detail_view), name="infra_servidor_netbox_detail"),
        ] + super().get_urls()

    def netbox_detail_view(self, request, device_id):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        device = get_server_detail(device_id)
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
        context = {**self.admin_site.each_context(request), **(extra_context or {}),
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

    def add_view(self, request, form_url="", extra_context=None):
        extra_context = dict( show_save=False, show_save_and_continue=True)
        self.readonly_fields = ("status","conta")
        self.fields = ["nome", "tipo", "tipo_uso", "datacenter", "descricao", "marca", "modelo", "serie", "patrimonio", "garantia", "consumo", "vinculado", "status", "conta", "servicos"]
        self.inlines = ()
        return super().add_view(request, form_url=form_url, extra_context=extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        servidor = get_object_or_404(Servidor, id=object_id)
        if servidor.tipo == 'Servidor Virtual' and  servidor.vm_ambiente_virtual:
            self.fields = ["nome", "tipo", "tipo_uso", "predio", "datacenter", "descricao", "status", "conta", "vm_remover", "servicos"]
        elif servidor.tipo == 'Servidor Virtual':
            self.fields = ["nome", "tipo", "tipo_uso", "predio", "datacenter", "descricao", "status", "conta", "servicos"]
        else:
            self.fields = ["nome", "tipo", "tipo_uso", "predio", "datacenter", "descricao", "marca", "modelo", "serie", "patrimonio", "garantia", "consumo", "vinculado", "status", "conta", "servicos"]

        self.readonly_fields = ("nome", "status", "conta", "tipo", "tipo_uso", "predio")
        self.inlines = [HostnameIPServidorInLine, GrupoAcessoEquipamentoInLine, OcorrenciaInLine, ServicoNagiosInLine, TenantsInLine, OperatingSystemInLine,]
        return super().change_view(request, object_id, form_url=form_url, extra_context=extra_context)

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


