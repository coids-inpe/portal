
from apps.biblioteca.models import Documento
import pytest
from django.test import RequestFactory
from django.urls import reverse
from apps.biblioteca.admin import DocumentoAdmin, GroupInLine
from apps.core.tests.base import *

pytestmark = pytest.mark.django_db

def test_admin_colaborador_secretaria_visualizar(admin_site, secretaria, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    documento = mixer.blend(Documento)
    documento.grupo.add(*secretaria.groups.all())
    request = RequestFactory().get(reverse('admin:biblioteca_documento_change', args=(documento.id,)))
    request.user = secretaria
    model_admin = DocumentoAdmin(Documento, admin_site)
    assert model_admin.inlines == [GroupInLine]
    assert model_admin.get_queryset(request).filter(pk=documento.pk).exists()
