from apps.infra.utils.netbox import get_device_data, get_storage_devices


STORAGE_ROLES = {"controller", "disk array", "storage"}


def _storage_role(device: dict) -> dict | None:
    role = device.get("role") or device.get("device_role") or {}
    names = {(role.get(key) or "").casefold().replace("-", " ") for key in ("slug", "name")}
    return role if names & STORAGE_ROLES else None


def _status(device: dict) -> str:
    status = device.get("status") or {}
    value = (status.get("value") or status.get("label") or "").casefold()
    return "Ativo" if value in {"active", "ativo"} else "Inativo" if value else "—"


def get_storage_inventory() -> list[dict] | None:
    devices = get_storage_devices()
    if devices is None:
        return None

    inventory = []
    for device in devices:
        role = _storage_role(device)
        if role is None:
            continue
        role_key = (role.get("name") or role.get("slug") or "").casefold().replace(" ", "-")
        inventory.append({
            "id": device["id"],
            "name": device.get("name") or device.get("display") or "Sem nome",
            "role": role.get("name") or "—",
            "role_key": role_key,
            "site": (device.get("site") or {}).get("name", "—"),
            "rack": (device.get("rack") or {}).get("name", "—"),
            "model": (device.get("device_type") or {}).get("model", "—"),
            "status": _status(device),
        })
    return inventory


def get_storage_detail(device_id: int) -> dict | None:
    device = get_device_data(device_id)
    if device is None:
        return None
    role = _storage_role(device)
    if role is None:
        return {}
    device_type = device.get("device_type") or {}
    return {
        "name": device.get("name") or device.get("display") or "Sem nome",
        "role": role.get("name") or "—",
        "status": _status(device),
        "manufacturer": (device_type.get("manufacturer") or {}).get("name", "—"),
        "model": device_type.get("model", "—"),
        "site": (device.get("site") or {}).get("name", "—"),
        "rack": (device.get("rack") or {}).get("name", "—"),
        "position": device.get("position"),
        "serial": device.get("serial") or "—",
        "asset_tag": device.get("asset_tag") or "—",
        "primary_ip": (device.get("primary_ip") or {}).get("address", "—"),
        "description": device.get("description") or "—",
    }
