from apps.noc.managers import ChecklistServidorNagiosServicoManager
from django.db import models

class Checklist(models.Model):
    turno = models.CharField(max_length=20)
    criado = models.DateTimeField( 'criado em', auto_now_add=True, auto_now=False)
    enviado = models.DateTimeField( blank=True, null=True)
    responsaveis = models.ManyToManyField('colaborador.Colaborador', through="ChecklistResponsaveis")
    alerta_monitoramento = models.ManyToManyField('infra.ServidorNagiosServico', blank=True, through="ChecklistServidorNagiosServico")
    outros = models.TextField('Geral', blank=True, null=True)

    class Meta :
        ordering = ['-criado','-turno',]

    def __str__(self):
        if self.criado:
            return f"{self.turno} | {self.criado.strftime('%Y-%m-%d %H:%M')}"
        else:
            return f"{self.turno}"

    @property
    def alertas_nagios(self):
        return self.checklistservidornagiosservico_set.all()


class ChecklistServidorNagiosServico(models.Model):
    checklist = models.ForeignKey("noc.Checklist", on_delete=models.CASCADE)
    alerta_monitoramento = models.ForeignKey("infra.ServidorNagiosServico", on_delete=models.CASCADE, blank=True, null=True)
    netbox_object_type = models.CharField(max_length=50, blank=True, default="", editable=False)
    netbox_object_id = models.PositiveBigIntegerField(blank=True, null=True, editable=False)
    equipamento_nome = models.CharField(max_length=255, blank=True, default="", editable=False)
    nagios_servico = models.ForeignKey("monitoramento.NagiosServicos", verbose_name="Serviço Nagios", on_delete=models.PROTECT, blank=True, null=True)
    servico_nome = models.CharField(max_length=255, blank=True, default="", editable=False)
    objects = ChecklistServidorNagiosServicoManager()

    def __str__(self):
        return f"{self.checklist} | {self.identificacao}"

    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()
        external = bool(self.netbox_object_type or self.netbox_object_id or self.equipamento_nome or self.nagios_servico_id or self.servico_nome)
        if self.alerta_monitoramento_id and not external:
            return
        if self.alerta_monitoramento_id or (
            self.netbox_object_type != "dcim.device"
            or not self.netbox_object_id or self.netbox_object_id < 1
            or not self.equipamento_nome.strip() or not self.nagios_servico_id
            or not self.servico_nome.strip()
        ):
            raise ValidationError("Informe um equipamento do NetBox e um serviço Nagios, ou preserve o vínculo antigo.")

    @property
    def identificacao(self):
        if self.alerta_monitoramento_id:
            return str(self.alerta_monitoramento)
        return f"{self.equipamento_nome} | {self.servico_nome}"

    @property
    def equipamento_url(self):
        from urllib.parse import urlsplit
        from apps.infra.utils.netbox import NETBOX_URL

        base = (NETBOX_URL or "").rstrip("/")
        if self.netbox_object_type == "dcim.device" and self.netbox_object_id and urlsplit(base).scheme in {"http", "https"}:
            return f"{base}/dcim/devices/{self.netbox_object_id}/"
        return ""


class ChecklistResponsaveis(models.Model):
    checklist = models.ForeignKey("noc.Checklist", on_delete=models.CASCADE)
    responsavel = models.ForeignKey("colaborador.Colaborador", on_delete=models.CASCADE)

    def __str__(self):
        return self.responsavel.full_name

class ChecklistEmail(models.Model):
    email = models.CharField(max_length=255)

    def __str__(self):
        return self.email
