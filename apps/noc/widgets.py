from django import forms
from django.urls import reverse


class NetBoxDeviceWidget(forms.Select):
    template_name = "noc/widgets/netbox_device.html"

    class Media:
        js = ("noc/netbox-device.js",)
        css = {"all": ("noc/netbox-device.css",)}

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["search_url"] = reverse("noc:netbox_devices")
        return context
