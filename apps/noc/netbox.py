"""Consultas do seletor NOC, sem alterar os contratos dos consumidores legados."""
import requests

from apps.infra.utils import netbox as client

PAGE_SIZE = 20


class NetBoxError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


def _get(path, params=None):
    if not client.NETBOX_URL or not client.NETBOX_TOKEN:
        raise NetBoxError("NetBox não configurado. Informe o administrador.")
    try:
        response = requests.get(
            f"{client.NETBOX_URL.rstrip('/')}/api/dcim/devices/{path}",
            params=params, headers=client._headers(), timeout=5,
            allow_redirects=False,
        )
        if response.status_code in (301, 302, 303, 307, 308):
            raise NetBoxError("Confira o endereço configurado do NetBox.")
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Resposta inválida")
        return data
    except requests.HTTPError as error:
        status = error.response.status_code
        if status == 404:
            raise NetBoxError("Equipamento não encontrado no NetBox. Faça uma nova busca.", 404) from error
        if status in (401, 403):
            raise NetBoxError("A credencial do portal não tem acesso aos equipamentos do NetBox.", 403) from error
        raise NetBoxError("NetBox indisponível. Tente novamente.") from error
    except (requests.RequestException, ValueError, TypeError, KeyError) as error:
        raise NetBoxError("Não foi possível consultar o NetBox. Tente novamente.") from error


def device_label(device):
    return " | ".join(str(value) for value in (
        device.get("name") or device.get("display") or f"Dispositivo #{device['id']}",
        (device.get("site") or {}).get("name"),
        (device.get("rack") or {}).get("name"),
    ) if value)


def search_devices(query, offset=0):
    data = _get("", {"q": query, "limit": PAGE_SIZE, "offset": offset})
    try:
        devices = data["results"]
        if not isinstance(devices, list):
            raise ValueError("Resultados inválidos")
        return {
            "results": [{"id": int(item["id"]), "label": device_label(item)} for item in devices],
            "more": bool(data.get("next")),
        }
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise NetBoxError("O NetBox retornou uma lista de equipamentos inválida.") from error


def get_device(device_id):
    if not isinstance(device_id, int) or device_id < 1:
        raise NetBoxError("Selecione um equipamento válido.", 400)
    data = _get(f"{device_id}/")
    if data.get("id") != device_id or not isinstance(data.get("name") or data.get("display"), str):
        raise NetBoxError("O NetBox retornou um equipamento inválido.")
    return data
