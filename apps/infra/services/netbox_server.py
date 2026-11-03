from apps.infra.utils.netbox import get_device_data, get_server_devices


SERVER_ROLES = {"server", "servidor"}


def _is_server(device):
    role = device.get("role") or device.get("device_role") or {}
    return bool({(role.get(key) or "").casefold() for key in ("name", "slug")} & SERVER_ROLES)


def _status(device):
    status = device.get("status") or {}
    value = (status.get("value") or status.get("label") or "").casefold()
    return "Ativo" if value in {"active", "ativo"} else "Inativo" if value else "—"


def get_server_inventory(limit=15, offset=0, search="", asset_tag=""):
    page = get_server_devices(limit=limit, offset=offset, search=search, asset_tag=asset_tag)
    if page is None:
        return None
    devices = [{
        "id": device["id"],
        "name": device.get("name") or device.get("display") or "Sem nome",
        "role": (device.get("role") or device.get("device_role") or {}).get("name") or "Servidor",
        "site": (device.get("site") or {}).get("name") or "—",
        "rack": (device.get("rack") or {}).get("name") or "—",
        "model": (device.get("device_type") or {}).get("model") or "—",
        "asset_tag": device.get("asset_tag") or "—",
        "status": _status(device),
    } for device in page.get("results", []) if device.get("id") is not None and _is_server(device)]
    return {
        "devices": devices,
        "count": page.get("count", len(devices)),
        "next_offset": offset + limit if page.get("next") else None,
        "previous_offset": max(0, offset - limit) if offset else None,
    }


def get_server_detail(device_id):
    device = get_device_data(device_id)
    if device is None:
        return None
    if not _is_server(device):
        return {}
    device_type = device.get("device_type") or {}
    return {
        "name": device.get("name") or device.get("display") or "Sem nome",
        "role": (device.get("role") or device.get("device_role") or {}).get("name") or "Servidor",
        "status": _status(device),
        "manufacturer": (device_type.get("manufacturer") or {}).get("name") or "—",
        "model": device_type.get("model") or "—",
        "site": (device.get("site") or {}).get("name") or "—",
        "rack": (device.get("rack") or {}).get("name") or "—",
        "position": device.get("position"),
        "serial": device.get("serial") or "—",
        "asset_tag": device.get("asset_tag") or "—",
        "primary_ip": (device.get("primary_ip") or {}).get("address") or "—",
        "description": device.get("description") or "—",
    }
