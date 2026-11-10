from django.db import migrations


def copy_operations(apps, schema_editor):
    Server = apps.get_model('infra', 'Servidor')
    Operations = apps.get_model('infra', 'NetBoxServerOperations')
    for server in Server.objects.exclude(netbox_object_type='').exclude(netbox_object_id__isnull=True).iterator(chunk_size=200):
        operation, _ = Operations.objects.get_or_create(
            netbox_object_type=server.netbox_object_type,
            netbox_object_id=server.netbox_object_id,
            defaults={'tipo_uso': server.tipo_uso or '', 'status': server.status or 'Manutenção',
                      'conta': server.conta or 'Aguardando'},
        )
        operation.grupos_acesso.add(*server.grupos_acesso.all())
        operation.nagios_servicos.add(*server.nagios_servicos.all())


class Migration(migrations.Migration):
    dependencies = [('infra', '0024_netboxserveroperations')]
    operations = [migrations.RunPython(copy_operations, migrations.RunPython.noop)]
