from types import SimpleNamespace

from apps.infra.models import NetBoxServerOperations
from apps.infra.services.server_registration import VIRTUAL, get_server_snapshot


def load_vm_target(device_id):
    operation = NetBoxServerOperations.objects.get(netbox_object_type=VIRTUAL, netbox_object_id=device_id)
    snapshot = get_server_snapshot(VIRTUAL, device_id)
    addresses = [(item['hostname'], item['ip']) for item in snapshot['netbox_ips']]
    if not addresses:
        raise OSError('Cadastre um IP no NetBox antes de criar a VM.')
    groups = ' | '.join(group.grupo_acesso for group in operation.grupos_acesso.all())
    return SimpleNamespace(
        id=[VIRTUAL, device_id], netbox_object_id=device_id, operation=operation,
        nome=snapshot['nome'], descricao=snapshot['descricao'], tipo_uso=operation.tipo_uso,
        host_principal=addresses[0], enderecos_operacionais=addresses,
        grupo_acesso_name=lambda: groups,
    )
