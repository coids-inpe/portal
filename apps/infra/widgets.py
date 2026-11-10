from django.urls import reverse
from apps.noc.widgets import NetBoxDeviceWidget


class ServidorNetBoxWidget(NetBoxDeviceWidget):
    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['search_url'] = reverse('admin:infra_servidor_netbox_search')
        context['widget']['attrs']['data-object-type-field'] = 'netbox_tipo'
        return context
