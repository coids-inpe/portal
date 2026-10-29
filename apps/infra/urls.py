from django.contrib.auth.decorators import login_required
from django.urls import path
from apps.infra.views import AlterarStatusServidorView, CriarServidorLocalView, CriarVmProgressView, CriarVmView, DataCenterView, GetNetboxRacksView, CriarServidorLdapView

app_name = "infra"

urlpatterns = [
    path("datacenter/netbox/racks/", GetNetboxRacksView.as_view(), name="netbox_racks"),
    path("datacenter/", DataCenterView.as_view(), name="datacenter"),
    path("servidor/<int:pk>/criarservidorldap/", login_required(CriarServidorLdapView.as_view()), name="criar_servidor_ldap"),
    path("servidor/<int:pk>/alterarstatus/", login_required(AlterarStatusServidorView.as_view()), name="alterar_servidor_status"),
    path("servidor/<int:pk>/criarservidorlocal/", login_required(CriarServidorLocalView.as_view()), name="criar_servidor_local"),
    path("servidor/<int:pk>/criarVM/", login_required(CriarVmView.as_view()), name="criar_vm"),
    path("servidor/<int:pk>/<template_id>/<task_id>/criarVM/progress", login_required(CriarVmProgressView.as_view()), name="criar_vm_progress"),
#     path("servidor/export_pdf/", export_servidor_to_pdf, name="infra_servidor_export_pdf"),
#     path("servidor/export_excel/", export_servidor_to_excel, name="infra_servidor_export_excel"),
#     path("storage/export_pdf/", export_storages_to_pdf, name="infra_storage_export_pdf"),
#     path("storage/export_excel/", export_storages_to_excel, name="infra_storage_export_excel"),
#     path("supercomputador/export_pdf/", export_supercomputador_to_pdf, name="infra_supercomputador_export_pdf"),
#     path("supercomputador/export_excel/", export_supercomputador_to_excel, name="infra_supercomputador_export_excel"),
#     path("partes_equipamento/export_pdf/", export_partes_equipamento_to_pdf, name="infra_equipamentoparte_export_pdf"),
#     path("partes_equipamento/export_excel/", export_partes_equipamento_to_excel, name="infra_equipamentoparte_export_excel"),
#     path("ambiente_virtual/export_pdf/", export_ambiente_virtual_to_pdf, name="infra_ambientevirtual_export_pdf"),
#     path("ambiente_virtual/export_excel/", export_ambiente_virtual_to_excel, name="infra_ambientevirtual_export_excel"),
#     path("templates/export_pdf/", export_templates_to_pdf, name="infra_templates_export_pdf"),
#     path("templates/export_excel/", export_templates_to_excel, name="infra_templates_export_excel"),
#     path("rack/export_pdf/", export_racks_to_pdf, name="infra_rack_export_pdf"),
#     path("rack/export_excel/", export_racks_to_excel, name="infra_rack_export_excel"),
#     path("hostnameip/export_pdf/", export_hostnameip_to_pdf, name="infra_hostnameip_export_pdf"),
#     path("hostnameip/export_excel/", export_hostnameip_to_excel, name="infra_hostnameip_export_excel"),
#     path("rede/export_pdf/", export_rede_to_pdf, name="infra_rede_export_pdf"),
#     path("rede/export_excel/", export_rede_to_excel, name="infra_rede_export_excel"),
]
