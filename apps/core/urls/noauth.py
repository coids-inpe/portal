from django.urls import path
from apps.core.views import EstruturaGruposView, CoreStatusView, export_grupoAcesso_to_pdf, export_grupoAcesso_to_excel

app_name = "core_open"

urlpatterns = [
    path("grupos/", EstruturaGruposView.as_view(), name="grupos"),
    path("status/", CoreStatusView.as_view(), name="status"),
    path('grupoAcesso/export_pdf/', export_grupoAcesso_to_pdf, name='core_grupoAcesso_export_pdf'),
    path('grupoAcesso/export_excel/', export_grupoAcesso_to_excel, name='core_grupoAcesso_export_excel'),
]
