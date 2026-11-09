
from apps.colaborador.models import Colaborador
from django import forms
from django.db.models import Q
from apps.noc.models import Checklist, ChecklistResponsaveis, ChecklistServidorNagiosServico
from apps.infra.models import Ocorrencia
from apps.noc.netbox import NetBoxError, get_device
from apps.noc.widgets import NetBoxDeviceWidget

class ChechlistForm(forms.ModelForm):
    
    TURNO = (
        ("Turno 1", "Turno 1"),
        ("Turno 2", "Turno 2"),
        ("Turno 3", "Turno 3"),
        ("Turno 4", "Turno 4"),
        ("Turno Extra", "Turno Extra"),
    )
    turno = forms.ChoiceField(choices = TURNO, initial='Analisando') 

    class Meta:
        model = Checklist
        fields = ["turno","outros"]
        widgets = {"outros": forms.Textarea(attrs={"cols": 80, "rows": 4})}


class ChechlistResponsaveisInlineForm(forms.ModelForm):
    responsavel = forms.ModelChoiceField(queryset=Colaborador.objects.filter(Q(groups__name="NOC") | Q(groups__name="Servicedesk") ).distinct(), label="Responsável", widget=forms.Select(attrs={"data-live-search": "True"}),required=False,)

    class Meta:
        model = ChecklistResponsaveis
        fields = ["responsavel"]

class ChecklistServidorNagiosServicoInlineForm(forms.ModelForm):
    netbox_device = forms.IntegerField(
        label="Equipamento (NetBox)", min_value=1, required=False,
        widget=NetBoxDeviceWidget,
    )

    class Meta:
        model = ChecklistServidorNagiosServico
        fields = ("netbox_device", "nagios_servico")
        widgets = {"nagios_servico": forms.Select(attrs={"data-live-search": "True"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        item = self.instance
        choices = [("", "Selecione um equipamento")]
        if item.netbox_object_id:
            self.initial["netbox_device"] = item.netbox_object_id
            choices.append((item.netbox_object_id, item.equipamento_nome))
        elif item.alerta_monitoramento_id:
            self.fields["netbox_device"].help_text = "Registro antigo: deixe equipamento e serviço vazios para manter o vínculo mostrado."
        if self.is_bound:
            selected = self.data.get(self.add_prefix("netbox_device"), "")
            if str(selected).isdigit() and str(selected) != str(item.netbox_object_id):
                choices.append((selected, f"Equipamento #{selected} — confirme pela busca"))
        self.fields["netbox_device"].widget.choices = choices

    def clean(self):
        cleaned = super().clean()
        if "netbox_device" in self.errors or "nagios_servico" in self.errors:
            return cleaned
        device_id = cleaned.get("netbox_device")
        service = cleaned.get("nagios_servico")
        item = self.instance
        if item.pk and item.alerta_monitoramento_id and not device_id and not service:
            return cleaned
        if not device_id:
            self.add_error("netbox_device", "Selecione um equipamento do NetBox.")
        if not service:
            self.add_error("nagios_servico", "Selecione um serviço Nagios.")
        if not device_id or not service:
            return cleaned
        if not item.pk or device_id != item.netbox_object_id:
            try:
                device = get_device(device_id)
            except NetBoxError as error:
                self.add_error("netbox_device", str(error))
                return cleaned
            name = device.get("name") or device.get("display")
            if not name or len(name) > 255:
                self.add_error("netbox_device", "O equipamento precisa ter um nome de até 255 caracteres no NetBox.")
                return cleaned
            item.equipamento_nome = name
        if service.pk != item.nagios_servico_id or not item.servico_nome:
            item.servico_nome = service.servico
        item.alerta_monitoramento = None
        item.netbox_object_type = "dcim.device"
        item.netbox_object_id = device_id
        self.fields["netbox_device"].widget.choices = [("", "Selecione um equipamento"), (device_id, item.equipamento_nome)]
        return cleaned


class NetBoxOcorrenciaForm(forms.ModelForm):
    netbox_device = forms.IntegerField(
        label="Equipamento (NetBox)", min_value=1, required=False,
        widget=NetBoxDeviceWidget,
    )

    class Meta:
        model = Ocorrencia
        fields = ("netbox_device", "descricao")
        widgets = {"descricao": forms.Textarea(attrs={"cols": 60, "rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        item = self.instance
        field = self.fields["netbox_device"]
        choices = [("", "Selecione um equipamento")]
        if item.netbox_object_id:
            self.initial["netbox_device"] = item.netbox_object_id
            choices.append((item.netbox_object_id, item.equipamento_identificacao))
        elif item.equipamento_id:
            field.help_text = f"Registro antigo: {item.equipamento_identificacao}. Deixe sem seleção para manter este vínculo."
        if self.is_bound:
            selected = self.data.get(self.add_prefix("netbox_device"), "")
            if str(selected).isdigit() and str(selected) != str(item.netbox_object_id):
                choices.append((selected, f"Equipamento #{selected} — confirme pela busca"))
        field.widget.choices = choices

    def clean_netbox_device(self):
        selected = self.cleaned_data["netbox_device"]
        item = self.instance
        if not selected:
            if item.pk and not item.netbox_object_id:
                return None
            raise forms.ValidationError("Selecione um equipamento do NetBox.")
        if item.pk and selected == item.netbox_object_id:
            return selected
        try:
            device = get_device(selected)
        except NetBoxError as error:
            raise forms.ValidationError(str(error)) from error
        name = device.get("name") or device.get("display")
        if not name or len(name) > 255:
            raise forms.ValidationError("O equipamento precisa ter um nome de até 255 caracteres no NetBox.")
        item.equipamento = None
        item.netbox_object_type = "dcim.device"
        item.netbox_object_id = selected
        item.equipamento_nome = name
        self.fields["netbox_device"].widget.choices = [("", "Selecione um equipamento"), (selected, name)]
        return selected
