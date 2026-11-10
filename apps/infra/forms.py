import re
from django import forms
from django.db.models import Q
from django.forms import ModelChoiceField
from apps.core.models import OperatingSystem, ServidorTenants, Tenants
from garb.forms import GarbForm

from apps.infra.models import Equipamento, EquipamentoGrupoAcesso, EquipamentoParte, HostnameIP, Ocorrencia, Servidor, ServidorHostnameIP, StorageAreaGrupoTrabalho, TemplateComando, TemplateVM
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.infra.services.server_registration import PHYSICAL, TYPES, NetBoxError, get_server_snapshot, update_server_inventory
from apps.infra.widgets import ServidorNetBoxWidget


class HostnameChoiceField(ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.hostname} | {obj.ip} | {obj.tipo.rede}"


class OcorrenciaForm(forms.ModelForm):
    class Meta:
        model = Ocorrencia
        descricao = forms.CharField()
        fields = ["equipamento", "descricao"]
        widgets = {"equipamento": forms.HiddenInput(), "descricao": forms.Textarea(attrs={"cols": 80, "rows": 2})}


class ServidorForm(forms.ModelForm):
    TIPOS_SERVIDOR = (
        ("", ""),
        ("Servidor Físico", "Servidor Físico"),
        ("Servidor Virtual", "Servidor Virtual"),
    )
    
    vm_remover = forms.BooleanField(required=False, label="Remover VM ")
    tipo = forms.ChoiceField(choices=TIPOS_SERVIDOR, )
    nome = HostnameChoiceField(queryset=HostnameIP.objects.filter(reservado=False).order_by('tipo'), label="Hostname", required=True, widget=forms.Select(attrs={"data-live-search": "True"}))
    vinculado = forms.ModelChoiceField(queryset=Equipamento.objects.filter(Q(tipo='storage') | Q(tipo='Supercomputador')), required=False, widget=forms.Select(attrs={"data-live-search": "True"}))

    class Meta:
        model = Servidor
        fields = ["nome", "tipo", "tipo_uso", "predio", "datacenter", "descricao", "marca", "modelo", "serie", "patrimonio", "garantia", "consumo", "vinculado", "status", "servicos"]

    def __init__(self, *args, **kwargs):
        super(ServidorForm, self).__init__(*args, **kwargs)
        if self.data.get("tipo") == "Servidor Virtual":
            self.fields["marca"].required = False
            self.fields["modelo"].required = False
            self.fields["consumo"].required = False
            self.fields["serie"].required = False
            self.fields["patrimonio"].required = False
            self.fields["servicos"].required = False


class HostnameIPForm(forms.ModelForm):
    reservado = forms.BooleanField(required=False)

    def clean_ip(self):
        ip = self.cleaned_data.get("ip")
        rede = str(self.cleaned_data.get("tipo")).split(' | ')[1]
        regular_expression_ip = re.match(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$", ip)
        if bool(regular_expression_ip) and all(map(lambda n: 0 <= int(n) <= 255, regular_expression_ip.groups())) and rede in ip:
            return ip
        raise ValidationError("Precisa de um ip válido")

    class Meta:
        model = HostnameIP
        fields = "__all__"


class HostnameIPInLineForm(forms.ModelForm):
    hostnameip = forms.ModelChoiceField(queryset=HostnameIP.objects.filter(reservado=False))

    class Meta:
        model = ServidorHostnameIP
        fields = ["hostnameip"]
        widgets = {"hostnameip": forms.Select(attrs={"data-live-search": "True"})}


class EquipamentoParteForm(forms.ModelForm):
    vinculado = forms.ModelChoiceField(queryset=Equipamento.objects.filter(Q(tipo='storage') | Q(tipo='Supercomputador')), required=False,)
    
    class Meta:
        model = EquipamentoParte
        fields = ["marca", "modelo","tipo_uso", "serie", "patrimonio", "predio", "garantia", "consumo", "vinculado", "descricao"]


class StorageAreaGrupoTrabalhoInLineForm(forms.ModelForm):
    class Meta:
        model = StorageAreaGrupoTrabalho
        fields = ["storage_area", "quota"]
        widgets = {"storage_area": forms.Select(attrs={"data-live-search": "True"})}


class TemplateComandoInLineForm(forms.ModelForm):
    TIPOS_Comando = (
        ("", ""),
        (1, "Comando Inicial"),
        (2, "Comando de Rede"),
        (3, "Comando Final"),
    )

    configuracao = forms.ChoiceField(choices = TIPOS_Comando) 
    class Meta:
        model = TemplateComando
        fields = ["comando", "configuracao", "prioridade"]
        

class EquipamentoGrupoAcessoForm(forms.ModelForm):
    class Meta:
        model = EquipamentoGrupoAcesso
        fields = ["grupo_acesso"]
        widgets = {"grupo_acesso": forms.Select(attrs={"data-live-search": "True"})}


class ServidorTenantsInLineForm(forms.ModelForm):
    class Meta:
        model = Tenants
        fields = ["tenants"]
        widgets = {"tenants": forms.Select(attrs={"data-live-search": "True"})}

class ServidorOperatingSystemInLineForm(forms.ModelForm):
    class Meta:
        model = OperatingSystem
        fields = ["so"]
        widgets = {"so": forms.Select(attrs={"data-live-search": "True"})}

class OcorrenciaInLineForm(forms.ModelForm):
    
    STATUS = (
        ("Analisando", "Analisando"),
        ("Aberto", "Aberto"),
        ("Fechado", "Fechado"),
        ("Suspenso", "Suspenso"),
    )
    status = forms.ChoiceField(choices = STATUS, initial='Analisando') 
    class Meta:
        model = Ocorrencia
        fields = ["ocorrencia", "descricao"]

    def __init__(self, *args, **kwargs):
        super(OcorrenciaInLineForm, self).__init__(*args, **kwargs)
        if str(self.instance.status) == "Fechado" and self.instance.ocorrencia != None :
            self.fields["ocorrencia"].widget.attrs["readonly"] = "readonly"
            self.fields["descricao"].widget.attrs["readonly"] = "readonly"
            self.fields["status"].widget.attrs["disabled"] = "disabled"


class AmbienteVirtualServidorInLineForm(forms.ModelForm):
    servidor = forms.ModelChoiceField(Servidor.objects.filter(tipo="Servidor Físico"), widget=forms.Select(attrs={"data-live-search": "True"}))

    class Meta:
        model = Servidor
        fields = ["servidor"]


class ServidorVMForm(GarbForm):
    CPU_CHOICES =( 
        ("1", "1"), 
        ("2", "2"), 
        ("4", "4"), 
        ("8", "8"), 
    ) 
    MEMORIA_CHOICES =( 
        ("2", "2"), 
        ("4", "4"), 
        ("8", "8"), 
        ("16", "16"), 
    ) 

    servidor = forms.IntegerField(widget=forms.HiddenInput())
    template = forms.ModelChoiceField(TemplateVM.objects.all(), widget=forms.Select(attrs={"data-live-search": "True"}))
    cpu = forms.ChoiceField(choices = CPU_CHOICES, initial='4') 
    memoria = forms.ChoiceField(label="Memória GB", initial='8', choices = MEMORIA_CHOICES) 

    class Meta:
        fieldsets = [
            ("Nova VM", {"fields": ("servidor","template", "cpu", "memoria")}),
        ]


class OcorrenciaChecklistInLineForm(forms.ModelForm):
    equipamento = forms.ModelChoiceField(Equipamento.objects.all().exclude(tipo='Servidor Virtual').order_by('tipo'), widget=forms.Select(attrs={"data-live-search": "True"}))

    class Meta:
        model = Ocorrencia
        fields = ("equipamento","descricao")



class NetBoxServidorForm(forms.ModelForm):
    netbox_tipo = forms.ChoiceField(label='Tipo no NetBox', choices=TYPES, required=False, initial=PHYSICAL)
    netbox_device = forms.IntegerField(label='Servidor (NetBox)', min_value=1, required=False, widget=ServidorNetBoxWidget)
    atualizar_netbox = forms.BooleanField(label='Atualizar identificação e IPs do NetBox ao salvar', required=False)
    nome = forms.CharField(label='Nome', max_length=255, required=False)
    serie = forms.CharField(label='Serial', max_length=255, required=False)
    patrimonio = forms.CharField(label='Patrimônio', max_length=255, required=False)
    descricao = forms.CharField(label='Descrição', max_length=255, required=False)

    class Meta:
        model = Servidor
        fields = ('tipo_uso', 'servicos', 'vinculado', 'vm_remover')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        item = self.instance
        choices = [('', 'Selecione um servidor')]
        if item.netbox_object_id:
            self.initial['netbox_tipo'] = item.netbox_object_type
            self.initial['netbox_device'] = item.netbox_object_id
            choices.append((item.netbox_object_id, item.nome))
            for field in ('nome', 'serie', 'patrimonio', 'descricao'):
                self.initial[field] = getattr(item, field) or ''
        elif item.pk and 'netbox_device' in self.fields:
            self.fields['netbox_device'].help_text = 'Registro antigo: deixe sem seleção para manter os vínculos atuais.'
        if self.is_bound:
            selected = self.data.get(self.add_prefix('netbox_device'), '')
            if str(selected).isdigit() and str(selected) != str(item.netbox_object_id):
                choices.append((selected, f'Servidor #{selected} — confirme pela busca'))
        if 'netbox_device' in self.fields:
            self.fields['netbox_device'].widget.choices = choices
        if 'servicos' in self.fields:
            self.fields['servicos'].required = False

    def clean(self):
        cleaned = super().clean()
        if 'netbox_device' in self.errors or 'netbox_tipo' in self.errors:
            return cleaned
        item = self.instance
        object_id = cleaned.get('netbox_device')
        kind = cleaned.get('netbox_tipo')
        if not object_id:
            if item.pk and not item.netbox_object_id and not cleaned.get('atualizar_netbox'):
                for field in ('nome', 'serie', 'patrimonio', 'descricao'):
                    cleaned[field] = getattr(item, field) or ''
                return cleaned
            self.add_error('netbox_device', 'Selecione um servidor do NetBox.')
            return cleaned
        if kind not in dict(TYPES):
            self.add_error('netbox_tipo', 'Selecione o tipo de servidor.')
            return cleaned
        if item.netbox_object_id and (object_id != item.netbox_object_id or kind != item.netbox_object_type):
            self.add_error('netbox_device', 'O vínculo existente não pode ser trocado por outro servidor.')
            return cleaned
        if Servidor.objects.filter(netbox_object_type=kind, netbox_object_id=object_id).exclude(pk=item.pk).exists():
            self.add_error('netbox_device', 'Este servidor já possui um registro operacional no portal.')
            return cleaned
        snapshot = None
        if not item.netbox_object_id or cleaned.get('atualizar_netbox'):
            try:
                snapshot = get_server_snapshot(kind, object_id)
            except NetBoxError as error:
                self.add_error('netbox_device', str(error))
                return cleaned
            for field, value in snapshot.items():
                setattr(item, field, value)
            item.netbox_object_type = kind
            item.netbox_object_id = object_id
            item.netbox_atualizado_em = timezone.now()
            self.fields['netbox_device'].widget.choices = [('', 'Selecione um servidor'), (object_id, item.nome)]
        changes = {field: cleaned[field] for field in ('nome', 'serie', 'patrimonio', 'descricao')
                   if field in self.data and field in cleaned and cleaned[field] != (getattr(item, field) or '')}
        if item.conta == 'FreeIPA':
            from apps.infra.utils.freeipa_location import get_rede_montagem
            try:
                get_rede_montagem(item)
            except OSError as error:
                self.add_error(None, str(error))
        if changes and not self.errors:
            try:
                update_server_inventory(kind, object_id, changes)
            except NetBoxError as error:
                self.add_error(None, str(error))
                return cleaned
            for field, value in changes.items():
                setattr(item, field, value)
            item.netbox_atualizado_em = timezone.now()
        for field in ('nome', 'serie', 'patrimonio', 'descricao'):
            cleaned[field] = getattr(item, field) or ''
        return cleaned
