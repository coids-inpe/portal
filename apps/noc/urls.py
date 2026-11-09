from apps.noc.views import EnviarCheckListView, netbox_devices
from django.urls import path

app_name = "noc"

urlpatterns = [
    path("netbox/devices/", netbox_devices, name="netbox_devices"),
    path("enviar/<int:pk>/", EnviarCheckListView.as_view(), name="checklist_enviar"),
    
]



