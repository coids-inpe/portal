
import base64
import io
import json
from itertools import chain

import pyqrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import (LoginRequiredMixin,
                                        PermissionRequiredMixin)
from django.db.models import Q
from django.http import HttpResponse, JsonResponse, HttpRequest
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, ListView
from django.views.generic.base import RedirectView, TemplateView
from django.views.generic.edit import CreateView, FormView
from django.template.loader import render_to_string
from garb.views import ViewContextMixin

from apps.core.models import Predio
from apps.core.tasks import send_email_task
from apps.core.utils.freeipa import FreeIPA
from apps.infra.forms import OcorrenciaForm, ServidorVMForm
from apps.infra.models import (Equipamento, EquipamentoParte,
                               Ocorrencia, Servidor, TemplateVM)
from apps.infra.utils.freeipa_location import Automount
from apps.infra.utils.history import HistoryInfra
from apps.infra.services.rack_visualization import RackVisualizationService
from apps.infra.utils.xen_crud import XenCrud
from apps.monitoramento.models.nagios import NagiosServicos
from apps.colaborador.utils import export_to_pdf, export_to_xlsx
from apps.infra.models import Storage, Servidor, Supercomputador, EquipamentoParte, AmbienteVirtual, TemplateVM, HostnameIP, Rede
from django.db.models import Sum
from reportlab.lib.pagesizes import landscape, A4

class DataCenterView(LoginRequiredMixin, TemplateView):
    template_name = "infra/datacenter/datacenter.html"


class CriarServidorLdapView(LoginRequiredMixin, PermissionRequiredMixin, RedirectView):
    permission_required = "infra.change_servidor"

    def get_redirect_url(self, *args, **kwargs):
        servidor = get_object_or_404(Servidor, id=kwargs["pk"])
        grupos_acesso = servidor.grupos_acesso.all()
        if grupos_acesso.exists() and servidor.conta == "Aguardando":
            client_feeipa = FreeIPA(self.request)
            if client_feeipa.set_host(servidor, description=servidor.descricao):
                automount = Automount(client_feeipa, servidor, self.request)
                automount.adicionar_grupos(grupos_acesso)
                automount.adicionar_oper()
                automount.adicionar_home()
                HistoryInfra(self.request).novo_servidor(servidor=servidor)
                send_email_task.delay("Servidor Criado",f"O Servidor: {servidor.nome} foi criado no FreeIPA, por:{self.request.user.username}",[settings.EMAIL_SYSADMIN])
                servidor.conta = "FreeIPA"
                servidor.save()
                messages.add_message(self.request, messages.WARNING, "Verifique as regras de export do storage!")
                if servidor.tipo == 'Servidor Virtual':
                    return reverse_lazy("infra:criar_vm", kwargs={"pk": servidor.id, })
        else:
            messages.add_message(self.request, messages.ERROR, "Confira o Cadastro, existe informação faltando ou não salva! É necessário um grupo de acesso! ")
        return reverse_lazy("admin:infra_servidor_change", kwargs={"object_id": servidor.id, })


class CriarServidorLocalView(LoginRequiredMixin, PermissionRequiredMixin, RedirectView):
    permission_required = "infra.change_servidor"

    def get_redirect_url(self, *args, **kwargs):
        servidor = get_object_or_404(Servidor, id=kwargs["pk"])
        grupos_acesso = servidor.grupos_acesso.all()
        if grupos_acesso.exists() and servidor.conta == "Aguardando":
            HistoryInfra(self.request).novo_servidor(servidor=servidor)
            send_email_task.delay("Servidor Criado",f"O Servidor: {servidor.nome} foi criado com conta Local, por:{self.request.user.username}",[settings.EMAIL_SYSADMIN])
            servidor.conta = "Local"
            servidor.save()
            if servidor.tipo == 'Servidor Virtual':
                return reverse_lazy("infra:criar_vm", kwargs={"pk": servidor.id, })
        else:
            messages.add_message(self.request, messages.ERROR, "Confira o Cadastro, existe informação faltando ou não salva! É necessário um grupo de acesso! ")
        return reverse_lazy("admin:infra_servidor_change", kwargs={"object_id": servidor.id, })

class AlterarStatusServidorView(LoginRequiredMixin, PermissionRequiredMixin, RedirectView):
    permission_required = "infra.view_servidor"

    def get_redirect_url(self, *args, **kwargs):
        servidor = get_object_or_404(Servidor, id=kwargs["pk"])
        if servidor.status == "Manutenção":
            servidor.status = "Em uso"
            nagios_servicos = NagiosServicos.objects.all().filter(padrao=True)
            servidor_nagios_servicos = servidor.nagios_servicos.all()
            [servidor.nagios_servicos.add(servico) for servico in nagios_servicos if servico not in servidor_nagios_servicos]
            servidor.save()
        else:
            servidor.status = "Manutenção"
            servidor.save()

        messages.add_message(self.request, messages.SUCCESS, "Status do Servidor Alterado!")
        HistoryInfra(self.request).status_servidor(servidor=servidor)
        send_email_task.delay("Mudança de Status do Servidor",f"O Servidor: {servidor.nome} teve seu status alterado para: {servidor.status} por:{self.request.user.username}",[settings.EMAIL_SYSADMIN, settings.EMAIL_SUPORTE])
        return reverse_lazy("admin:infra_servidor_change", kwargs={"object_id": servidor.id, })



class CriarVmView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    form_class = ServidorVMForm
    template_name = "infra/servidor/vm.html"
    permission_required = "infra.change_servidor"
    task = 0

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = ServidorVMForm(initial={'servidor': self.kwargs['pk'] })
        context["opts"] = Servidor._meta
        context["original"] = get_object_or_404(Servidor, id=self.kwargs['pk'])
        context["template"] = 0
        return context
    
    def form_valid(self, form):
        vm = get_object_or_404(Servidor, id=form.cleaned_data['servidor'])
        self.template = form.cleaned_data['template']
        memoria = form.cleaned_data['memoria']
        cpu = form.cleaned_data['cpu']
        self.task = XenCrud(self.request, vm, self.template.ambiente_virtual).create_vm(self.template, memoria, cpu)
        if not self.task:
            return super().form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("infra:criar_vm_progress", kwargs={"pk": self.kwargs['pk'], "task_id": self.task.id, "template_id": self.template.id  })

class CriarVmProgressView(LoginRequiredMixin, TemplateView):
    template_name = "infra/servidor/vm.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["opts"] = Servidor._meta
        context["original"] = get_object_or_404(Servidor, id=self.kwargs['pk'])
        context["template"] = get_object_or_404(TemplateVM, id=self.kwargs['template_id'])
        context["task_id"] = self.kwargs['task_id'] 
        return context



# Exportar servidores
def export_servidor_to_pdf(request):
    queryset = Servidor.objects.all()
    page_title = "Relatório de Servidores"
    return export_to_pdf(
        queryset=queryset,
        fields={
            "nome": "Nome",
            "tipo": "Tipo",
            "tipo_uso": "Tipo de Uso",
            "datacenter": "Data Center",
            "descricao": "Descrição",
            "grupo": "Grupo",
            "responsavel_grupo": "Responsável Grupo",
            "status": "Status"
        },
        filename="servidores__.pdf",
        page_title=page_title,
        pagesize=landscape(A4)
    )

def export_servidor_to_excel(request):
    queryset = Servidor.objects.all()
    return export_to_xlsx(
        queryset,
        fields={
            "nome": "Nome",
            "tipo": "Tipo",
            "tipo_uso": "Tipo de Uso",
            "datacenter": "Data Center",
            "descricao": "Descrição",
            "grupo": "Grupo",
            "responsavel": "Responsável",
            "status": "Status"
        },
        title="Relatório de Servidores",
        filename="servidores.xlsx"
    )


# Exportar Storages
def export_storages_to_pdf(request):
    queryset = Storage.objects.all()
    page_title = "Relatório de Storages"
    processed_queryset = []

    for storage in queryset:
        storage.capacidade_value = f"{storage.capacidade():.2f}"
        processed_queryset.append(storage)

    return export_to_pdf(
        queryset=processed_queryset,
        fields={
            "marca": "Marca",
            "modelo": "Modelo",
            "descricao": "Descrição",
            "capacidade_value": "Capacidade"
        },
        filename="storages.pdf",
        page_title=page_title
    )

def export_storages_to_excel(request):
    queryset = Storage.objects.all()
    processed_queryset = []
    
    for storage in queryset:
        storage.capacidade_value = f"{storage.capacidade():.2f}"  
        processed_queryset.append(storage)
    
    return export_to_xlsx(
        queryset=processed_queryset,
        fields={
            "marca": "Marca",
            "modelo": "Modelo",
            "descricao": "Descrição",
            "capacidade_value": "Capacidade"
        },
        title="Relatório de Storages",
        filename="storages.xlsx"
    )



# Exportar Supercomputador
def export_supercomputador_to_pdf(request):
    queryset = Supercomputador.objects.all()
    page_title = "Relatório de Supercomputadores"
    return export_to_pdf(queryset=queryset, fields=["marca", "modelo", "kafka_topico_realtime", "kafka_topico_historico"], filename="supercomputador__.pdf", page_title=page_title)

def export_supercomputador_to_excel(request):
    queryset = Supercomputador.objects.all()
    return export_to_xlsx(queryset, fields=["marca", "modelo", "kafka_topico_realtime", "kafka_topico_historico"], title="Relatório de Supercomputadores", filename="supercomputador.xlsx")

# Exportar Partes de Equipamento
def export_partes_equipamento_to_pdf(request):
    queryset = EquipamentoParte.objects.all()
    page_title = "Relatório de Partes de Equipamento"
    return export_to_pdf(queryset=queryset, fields=["patrimonio", "marca", "modelo", "vinculado", "status"], filename="partes_equipamento__.pdf", page_title=page_title)

def export_partes_equipamento_to_excel(request):
    queryset = EquipamentoParte.objects.all()
    return export_to_xlsx(queryset, fields=["patrimonio", "marca", "modelo", "vinculado", "status"], title="Relatório de Partes de Equipamento", filename="partes_equipamento.xlsx")

# Exportar Ambiente virtual
def export_ambiente_virtual_to_pdf(request):
    queryset = AmbienteVirtual.objects.all()
    page_title = "Relatório de Ambientes Virtuais"
    return export_to_pdf(queryset=queryset, fields=["nome", "virtualizador", "versao", "status"], filename="ambiente_virtual__.pdf", page_title=page_title)

def export_ambiente_virtual_to_excel(request):
    queryset = AmbienteVirtual.objects.all()
    return export_to_xlsx(queryset, fields=["nome", "virtualizador", "versao", "status"], title="Relatório de Ambientes Virtuais", filename="ambiente_virtual.xlsx")

# Exportar Templates
def export_templates_to_pdf(request):
    queryset = TemplateVM.objects.all()
    page_title = "Relatório de Templates"
    return export_to_pdf(queryset=queryset, fields=["nome", "configuracao", "ambiente_virtual"], filename="templates__.pdf", page_title=page_title)

def export_templates_to_excel(request):
    queryset = TemplateVM.objects.all()
    return export_to_xlsx(queryset, fields=["nome", "configuracao", "ambiente_virtual"], title="Relatório de Templates", filename="templates.xlsx")

# Exportar Racks
def export_racks_to_pdf(request):
    queryset = Rack.objects.all()
    page_title = "Relatório de Racks"
    processed_queryset = []

    for rack in queryset:
        rack.qtd_equip = rack.equipamento_set.count()
        consumo_total = rack.equipamento_set.aggregate(Sum("consumo"))["consumo__sum"]
        rack.consumo_eqp = consumo_total if consumo_total is not None else "-"
        processed_queryset.append(rack)

    return export_to_pdf(
        queryset=processed_queryset,
        fields={
            "rack": "Rack",
            "qtd_equip": "Qtd. Eqp.",
            "consumo": "Consumo Limite",
            "consumo_eqp": "Consumo Eqp.",
            "pdu1": "Primeiro PDU",
            "pdu2": "Segundo PDU"
        },
        filename="racks__.pdf",
        page_title=page_title
    )

def export_racks_to_excel(request):
    queryset = Rack.objects.all()
    page_title = "Relatório de Racks"

    processed_queryset = []
    for rack in queryset:
        setattr(rack, "Qtd. Eqp.", rack.equipamento_set.count())
        consumo_total = rack.equipamento_set.aggregate(Sum("consumo"))["consumo__sum"]
        setattr(rack, "Consumo Eqp.", consumo_total if consumo_total is not None else "-")
        processed_queryset.append(rack)

    return export_to_xlsx(
        queryset=processed_queryset,
        fields={
            "rack": "Rack",
            "Qtd. Eqp.": "Qtd. Equipamentos",
            "predio": "Prédio",
            "consumo": "Consumo Limite",
            "Consumo Eqp.": "Consumo dos Equipamentos",
            "pdu1": "Primeiro PDU",
            "pdu2": "Segundo PDU"
        },
        title=page_title,
        filename="racks.xlsx"
    )


# Exportar HostnameIP
def export_hostnameip_to_pdf(request):
    queryset = HostnameIP.objects.all()
    page_title = "Relatório de Hostname e IPs"
    return export_to_pdf(queryset=queryset, fields=["hostname", "ip", "reservado"], filename="hostnames-ips__.pdf", page_title=page_title)

def export_hostnameip_to_excel(request):
    queryset = HostnameIP.objects.all()
    return export_to_xlsx(queryset, fields=["hostname", "ip", "reservado"], title="Relatório de Hostname e IPs", filename="hostnames-ips.xlsx")

# Exportar Rede
def export_rede_to_pdf(request):
    queryset = Rede.objects.all()
    page_title = "Relatório de Redes"
    return export_to_pdf(queryset=queryset, fields=["rede", "ip", "prioridade_montagem"], filename="redes__.pdf", page_title=page_title)

def export_rede_to_excel(request):
    queryset = Rede.objects.all()
    return export_to_xlsx(queryset, fields=["rede", "ip", "prioridade_montagem"], title="Relatório de Redes", filename="redes.xlsx")

# Consulta os racks do NetBox para a página de ocupação.
class GetNetboxRacksView(LoginRequiredMixin, TemplateView):

    template_name = "infra/rack/netbox_racks.html"
    page_size = 12

    def get(self, request: HttpRequest, *args, **kwargs):
    
        context = self.get_context_data(**kwargs)

        # "Carregar mais" pede apenas os cartões da próxima página.
        if request.GET.get("partial") == "1":

            # Renderiza só o trecho HTML que será acrescentado à lista atual.
            cards_html = render_to_string(
                "infra/rack/_netbox_rack_cards.html", context, request=request
            )

            # O navegador usa next_offset para saber de onde carregar depois.
            response_data = {
                "html": cards_html,
                "next_offset": context["next_offset"],
            }

            # Uma falha na consulta ao NetBox é sinalizada nesta resposta parcial.
            if context["netbox_error"]:
                status_code = 502
            else:
                status_code = 200

            return JsonResponse(response_data, status=status_code)

        # Sem "partial=1", entrega a página completa na primeira visita.
        return self.render_to_response(context)


    def get_context_data(self, **kwargs):
        
        # Mantém os dados que a TemplateView já coloca no contexto.
        context = super().get_context_data(**kwargs)
        context["title"] = "Racks do NetBox"

        # Lê os filtros e a posição da página na URL. O service consulta o
        # NetBox e devolve os grupos, racks, total e próximo offset.
        context.update(RackVisualizationService().build_page(
            search_query=self.request.GET.get("q", ""),
            selected_group=self.request.GET.get("group", ""),
            offset=self.request.GET.get("offset", 0),
            page_size=self.page_size,
        ))

        # O template usa essas chaves para desenhar a página.
        return context
