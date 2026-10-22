from django.db import models


class Prometheus(models.Model):
    jobname = models.CharField("jobname", max_length=255)
    porta = models.IntegerField("porta")

    class Meta:
        verbose_name = "Prometheus"
        verbose_name_plural = "Prometheus"

    def __str__(self):
        return self.jobname
