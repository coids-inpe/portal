"""Identificação de servidores do NetBox para os fluxos operacionais do portal."""
from ipaddress import ip_interface
from urllib.parse import urlencode

import requests

from apps.infra.utils import netbox as client
from apps.infra.services.netbox_server import _is_server, get_server_inventory
from apps.noc.netbox import NetBoxError

PHYSICAL = 'dcim.device'
VIRTUAL = 'virtualization.virtualmachine'
TYPES = ((PHYSICAL, 'Servidor físico'), (VIRTUAL, 'Máquina virtual'))


def _get(path):
    if not client.NETBOX_URL or not client.NETBOX_TOKEN:
        raise NetBoxError('NetBox não configurado. Informe o administrador.')
    try:
        response = requests.get(f"{client.NETBOX_URL.rstrip('/')}/api/{path}", headers=client._headers(), timeout=5, allow_redirects=False)
        if 300 <= response.status_code < 400:
            raise NetBoxError('Confira o endereço configurado do NetBox.')
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError('Resposta inválida')
        return result
    except requests.HTTPError as error:
        if error.response.status_code == 404:
            raise NetBoxError('Servidor não encontrado no NetBox.', 404) from error
        if error.response.status_code in (401, 403):
            raise NetBoxError('A credencial do portal não tem acesso a estes dados no NetBox.', 403) from error
        raise NetBoxError('NetBox indisponível. Tente novamente.') from error
    except (requests.RequestException, ValueError, TypeError) as error:
        raise NetBoxError('Não foi possível consultar o NetBox. Tente novamente.') from error


def search_servers(kind, query='', offset=0):
    if kind not in dict(TYPES):
        raise NetBoxError('Tipo de servidor inválido.', 400)
    if kind == PHYSICAL:
        try:
            page = get_server_inventory(limit=20, offset=offset, search=query)
            if page is None:
                raise NetBoxError('Não foi possível consultar os servidores do NetBox.')
            return {'results': [{'id': item['id'], 'label': ' | '.join(str(item[key]) for key in ('name', 'site', 'rack'))} for item in page['devices']], 'more': page['next_offset'] is not None}
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise NetBoxError('O NetBox retornou uma lista de servidores inválida.') from error
    page = _get('virtualization/virtual-machines/?' + urlencode({'q': query, 'limit': 20, 'offset': offset}))
    try:
        if not isinstance(page['results'], list):
            raise ValueError
        return {'results': [{'id': int(item['id']), 'label': ' | '.join(value for value in (item['name'], (item.get('cluster') or {}).get('name')) if value)} for item in page['results']], 'more': bool(page.get('next'))}
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise NetBoxError('O NetBox retornou uma lista de VMs inválida.') from error


def get_server_snapshot(kind, object_id):
    if kind not in dict(TYPES) or not isinstance(object_id, int) or object_id < 1:
        raise NetBoxError('Selecione um servidor válido.', 400)
    endpoint = 'dcim/devices' if kind == PHYSICAL else 'virtualization/virtual-machines'
    item = _get(f'{endpoint}/{object_id}/')
    try:
        if item['id'] != object_id or not isinstance(item['name'], str) or not item['name'].strip():
            raise ValueError
        if kind == PHYSICAL and not _is_server(item):
            raise NetBoxError('Selecione um dispositivo com papel Server/Servidor no NetBox.', 400)
        device_type = item.get('device_type') or {}
        snapshot = {
            'nome': item['name'], 'tipo': 'Servidor Físico' if kind == PHYSICAL else 'Servidor Virtual',
            'marca': (device_type.get('manufacturer') or {}).get('name') or '',
            'modelo': device_type.get('model') or '', 'serie': item.get('serial') or '',
            'patrimonio': item.get('asset_tag') or '', 'descricao': item.get('description') or '',
            'netbox_localizacao': ' / '.join(str(value) for value in ((item.get('site') or {}).get('name'), (item.get('rack') or item.get('cluster') or {}).get('name')) if value),
        }
        if any(not isinstance(value, str) or len(value) > 255 for value in snapshot.values()):
            raise ValueError
        snapshot['comments'] = item.get('comments') or ''
        raw_ips = []
        primary = item.get('primary_ip') or item.get('primary_ip4') or item.get('primary_ip6')
        if primary:
            raw_ips.append(primary)
        filter_key = 'device_id' if kind == PHYSICAL else 'virtual_machine_id'
        offset = 0
        while True:
            page = _get(f'ipam/ip-addresses/?{filter_key}={object_id}&limit=100&offset={offset}')
            records = page['results']
            if not isinstance(records, list) or (page.get('next') and not records):
                raise ValueError
            raw_ips.extend(records)
            if not page.get('next'):
                break
            offset += len(records)
        addresses = {}
        for record in raw_ips:
            address = str(ip_interface(record['address']).ip)
            hostname = record.get('dns_name') or snapshot['nome']
            if not isinstance(hostname, str) or len(hostname) > 255:
                raise ValueError
            if address not in addresses:
                addresses[address] = {'hostname': hostname, 'ip': address}
            elif record.get('dns_name'):
                addresses[address]['hostname'] = hostname
        snapshot['netbox_ips'] = list(addresses.values())
        return snapshot
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise NetBoxError('Identificação ou endereços inválidos no NetBox. Confira o cadastro do servidor.') from error


def update_server_inventory(kind, object_id, values):
    if kind not in dict(TYPES) or not isinstance(object_id, int) or object_id < 1:
        raise NetBoxError('Servidor inválido.', 400)
    if not client.NETBOX_URL or not client.NETBOX_TOKEN:
        raise NetBoxError('NetBox não configurado. Informe o administrador.')
    endpoint = 'dcim/devices' if kind == PHYSICAL else 'virtualization/virtual-machines'
    payload = {remote: values[local] for local, remote in (
        ('nome', 'name'), ('serie', 'serial'), ('patrimonio', 'asset_tag'),
        ('descricao', 'description'), ('comentarios', 'comments')) if local in values}
    if not payload:
        return
    try:
        response = requests.patch(
            f"{client.NETBOX_URL.rstrip('/')}/api/{endpoint}/{object_id}/",
            headers=client._headers(), json=payload, timeout=5, allow_redirects=False)
        if 300 <= response.status_code < 400:
            raise NetBoxError('Confira o endereço configurado do NetBox.')
        if response.status_code in (401, 403):
            raise NetBoxError('A credencial do portal não pode alterar este servidor no NetBox.', 403)
        if response.status_code == 404:
            raise NetBoxError('Servidor não encontrado no NetBox.', 404)
        response.raise_for_status()
    except requests.RequestException as error:
        raise NetBoxError('Não foi possível salvar os dados no NetBox. Tente novamente.') from error
