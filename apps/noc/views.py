from django.core.mail import send_mail
from apps.infra.models import Ocorrencia
from django.conf import settings
from django.template.loader import get_template
from apps.noc.models import Checklist, ChecklistEmail
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, render
from django.views.generic.base import RedirectView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from apps.noc.netbox import NetBoxError, search_devices

class EnviarCheckListView(LoginRequiredMixin, PermissionRequiredMixin, RedirectView):
    permission_required = "noc.change_checklist"

    def get_redirect_url(self, *args, **kwargs):
        checklist = get_object_or_404(Checklist, id=kwargs["pk"])
        context = {'checklist': checklist, 'ocorrencias_abertas': Ocorrencia.objects.all().exclude(status="Fechado").exclude(checklist=checklist)}
        template_email = get_template('noc/email/checklist.html').render(context)
        emails = [checklist_email.email for checklist_email in ChecklistEmail.objects.all()]
        messages.add_message(self.request, messages.SUCCESS, "Checklist enviado!")
        try:
            send_mail(f"checklist {checklist}", None, settings.EMAIL_HOST_USER, emails, html_message=template_email)
        except Exception as error:
            print('#'*30)
            print(error)


        return reverse_lazy("admin:noc_checklist_change", kwargs={"object_id": checklist.id, })


@login_required
@require_GET
def netbox_devices(request):
    user = request.user
    checklist_access = user.has_perm("noc.add_checklist") or user.has_perm("noc.change_checklist")
    occurrence_access = user.has_perm("infra.add_ocorrencia") or user.has_perm("infra.change_ocorrencia")
    if not user.is_staff or not checklist_access or not occurrence_access:
        return JsonResponse({"error": "Sem permissão para selecionar equipamentos nas ocorrências."}, status=403)
    query = request.GET.get("q", "").strip()
    try:
        offset = int(request.GET.get("offset", "0"))
        if offset < 0 or offset > 1000000 or len(query) > 200:
            raise ValueError
    except ValueError:
        return JsonResponse({"error": "Busca ou página inválida."}, status=400)
    try:
        result = search_devices(query, offset)
    except NetBoxError as error:
        return JsonResponse({"error": str(error)}, status=error.status)
    response = JsonResponse(result)
    response["Cache-Control"] = "no-store"
    return response
