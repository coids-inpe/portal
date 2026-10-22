from __future__ import absolute_import, unicode_literals

import subprocess

from apps.core.models import GrupoTrabalho
from apps.core.utils.history import HistoryCore
from apps.core.utils.updategrupo import UpdateColaboradorGrupo, UpdateGrupoAcesso, UpdateGrupoVerificaDisco
from celery import Celery, shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import get_template
from django.contrib.auth import get_user_model
from apps.core.utils.freeipa import FreeIPA


def create_context(contexts_email):
    context = {}
    for context_email in contexts_email:
        context[context_email[0]] = context_email[1]
    return context


@shared_task(bind=True)
def send_email_template_task(self, subject, template, list_send_email, contexts_email):
    context = create_context(contexts_email)
    template_email = get_template(template).render(context)
    send_mail(subject, None, settings.EMAIL_HOST_USER, list_send_email, html_message=template_email)
    return subject + " | " + " ".join(str(e) for e in list_send_email)

@shared_task(bind=True)
def send_email_task(self, subject, text, list_send_email):
    send_mail(subject, text, settings.EMAIL_HOST_USER, list_send_email)
    return subject + " | " + " ".join(str(e) for e in list_send_email)

@shared_task
def rodar_scripts_netapp():
    try:
        result1 = subprocess.run(
            ['python3', '-m', 'apps.core.utils.listar_volumes.netapp_buscar_volumes'],
            capture_output=True,
            text=True,
            check=True
        )
        print("stdout 1:", result1.stdout)
    except Exception as err:
        print("Erro ao buscar volumes:", err)

    try:
        result2 = subprocess.run(
            ['python3', '-m', 'apps.core.utils.listar_montagem_volumes.netapp_montar_volumes'],
            capture_output=True,
            text=True,
            check=True
        )
        print("stdout 2:", result2.stdout)
    except Exception as err:
        print("Erro ao montar volumes:", err)
