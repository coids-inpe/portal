from django.views.generic import TemplateView
from apps.monitoramento.utils.xen import XenInfo
from apps.infra.models import AmbienteVirtual
from garb.views import ViewContextMixin


class XenView(ViewContextMixin, TemplateView):
    template_name = "monitoramento/vm/xen.html"
    title = "Ambiente Virtual"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ambientes = AmbienteVirtual.objects.filter
        ambientes_ativos = AmbienteVirtual.objects.filter(status="ON")
        ambientes_inativos = AmbienteVirtual.objects.filter(status="OFF")
        context["ambientes"] = ambientes
        context["ambientes_ativos"] = ambientes_ativos
        context["ambientes_inativos"] = ambientes_inativos
        return context


class XenPoolView(TemplateView):
    template_name = "monitoramento/vm/xen_pool.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ambiente = AmbienteVirtual.objects.get(pk=kwargs["pk"])
        context["title"] = str(ambiente)
        context["ambiente"] = ambiente
        return context


class XenPoolListView(TemplateView):
    template_name = "monitoramento/vm/xen_pool_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ambiente = AmbienteVirtual.objects.get(pk=kwargs["pk"])
        servidores = [servidor.nome for servidor in ambiente.servidor.all()]
        xen_info = XenInfo(ambiente=str(ambiente), servidores=servidores, ambiente_virtual=ambiente)
        context["title"] = ambiente
        context["pool"] = xen_info.carregar()
        return context
