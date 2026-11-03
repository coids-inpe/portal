from apps.infra.services.netbox_storage import get_storage_inventory
from apps.infra.utils.netbox import (
    get_ip_addresses, get_prefixes, get_rack_data, get_rack_elevation, get_server_devices, get_sites,
)


def _site_status(value):
    if isinstance(value, dict):
        value = value.get("value") or value.get("label") or ""
    return {"active": "Ativo", "inactive": "Inativo", "offline": "Inativo"}.get(
        str(value).casefold(), value or "—"
    )


def build_dashboard():
    racks = get_rack_data()
    servers = get_server_devices(limit=1)
    sites = get_sites()
    storages = get_storage_inventory()
    ips = get_ip_addresses()
    networks = get_prefixes()

    totals = {
        "racks": len(racks) if racks is not None else None,
        "devices": sum(rack.get("device_count") or 0 for rack in racks) if racks is not None else None,
        "servers": servers.get("count") if servers is not None else None,
        "storages": sum(device.get("role_key") != "controller" for device in storages) if storages is not None else None,
        "ips": len(ips) if ips is not None else None,
        "networks": len(networks) if networks is not None else None,
    }
    site_cards = []
    for site in sites or []:
        site_racks = [rack for rack in racks or [] if (rack.get("site") or {}).get("id") == site.get("id")]
        site_cards.append({
            "name": site.get("name") or site.get("display") or "Sem nome",
            "status": _site_status(site.get("status")),
            "region": (site.get("region") or {}).get("name") or "—",
            "description": site.get("description") or "",
            "rack_count": len(site_racks) if racks is not None else None,
            "device_count": sum(rack.get("device_count") or 0 for rack in site_racks) if racks is not None else None,
        })

    rack_highlights = []
    for rack in sorted(racks or [], key=lambda item: item.get("device_count") or 0, reverse=True)[:5]:
        height = rack.get("u_height") or 0
        elevation = get_rack_elevation(rack["id"], "front") if height else None
        occupied = None
        if elevation is not None:
            positions = {unit.get("id") for unit in elevation if unit.get("occupied")}
            start = rack.get("starting_unit") or 1
            occupied = sum(number in positions or number + 0.5 in positions for number in range(start, start + height))
        rack_highlights.append({
            "name": rack.get("name") or rack.get("display") or "Sem nome",
            "site": (rack.get("site") or {}).get("name") or "—",
            "devices": rack.get("device_count") or 0,
            "occupied": occupied,
            "height": height,
            "percent": round(occupied / height * 100) if occupied is not None and height else None,
        })

    return {
        "totals": totals,
        "sites": site_cards,
        "sites_error": sites is None,
        "rack_highlights": rack_highlights,
        "data_unavailable": any(value is None for value in (racks, servers, sites, storages, ips, networks)),
    }
