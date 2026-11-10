from django.db import migrations


def copy_vm_state(apps, schema_editor):
    Server = apps.get_model('infra', 'Servidor')
    Operations = apps.get_model('infra', 'NetBoxServerOperations')
    for server in Server.objects.filter(netbox_object_type='virtualization.virtualmachine').exclude(netbox_object_id__isnull=True).iterator(chunk_size=200):
        Operations.objects.filter(
            netbox_object_type=server.netbox_object_type,
            netbox_object_id=server.netbox_object_id,
        ).update(vm_remover=bool(server.vm_remover), vm_ambiente_virtual_id=server.vm_ambiente_virtual_id)


class Migration(migrations.Migration):
    dependencies = [('infra', '0026_netboxserveroperations_vm_ambiente_virtual_and_more')]
    operations = [migrations.RunPython(copy_vm_state, migrations.RunPython.noop)]
