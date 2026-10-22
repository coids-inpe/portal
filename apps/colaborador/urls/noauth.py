from django.urls import path
from apps.colaborador.views import InicioView, NovoView, SucessoView, export_colaboradores_to_pdf, export_colaboradores_to_excel, export_vpn_to_excel, export_vpn_to_pdf, export_divisao_to_pdf, export_divisao_to_excel
from django.contrib.auth import views as auth_views

app_name = "colaborador_open"

urlpatterns = [
    path("inicio/", InicioView.as_view(), name="inicio"),
    path("inicio/novo/", NovoView.as_view(), name="novo"),
    path("sucesso/", SucessoView.as_view(), name="sucesso"),
    path('colaborador/export_excel/', export_colaboradores_to_excel, name='colaborador_colaborador_export_excel'),
    path('colaborador/export_pdf/', export_colaboradores_to_pdf, name='colaborador_colaborador_export_pdf'),
    path('vpn/export_excel/', export_vpn_to_excel, name='colaborador_vpn_export_excel'),
    path('vpn/export_pdf/', export_vpn_to_pdf, name='colaborador_vpn_export_pdf'),
    path('divisao/export_pdf/', export_divisao_to_pdf, name='colaborador_divisao_export_pdf'),
    path('divisao/export_excel/', export_divisao_to_excel, name='colaborador_divisao_export_excel')
]
