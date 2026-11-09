
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
    class Meta:
        model = ChecklistServidorNagiosServico
        fields = ["alerta_monitoramento"]
        widgets = {"alerta_monitoramento": forms.Select(attrs={"data-live-search": "True"})}

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
