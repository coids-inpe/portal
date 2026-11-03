import os
from typing import Any
from urllib.parse import urlencode

import requests

NETBOX_URL = os.getenv("NETBOX_URL")
NETBOX_TOKEN = os.getenv("NETBOX_TOKEN")
NetBoxObject = dict[str, Any]


def _headers() -> dict[str, str]:
    if NETBOX_TOKEN and NETBOX_TOKEN.startswith("nbt_"):
        authentication_type = "Bearer"
    else:
        authentication_type = "Token"

    return {
        "Authorization": f"{authentication_type} {NETBOX_TOKEN}",
        "Accept": "application/json",
    }


def _get_paginated(url: str | None) -> list[NetBoxObject] | None:
    results: list[NetBoxObject] = []
    headers = _headers()

    try:
        while url:
            response = requests.get(url, headers=headers, timeout=5)

            response.raise_for_status()
            
            page = response.json()

            results.extend(page["results"])
            
            url = page.get("next")

        return results
    
    except (requests.exceptions.RequestException, ValueError, KeyError, TypeError) as error:
        print(f"Erro ao consultar o NetBox: {error}")
        return None
    

def _get_json(url: str) -> NetBoxObject | None:

    try:
        response = requests.get(url, headers=_headers(), timeout=5)

        response.raise_for_status()
        
        return response.json()
    
    except requests.exceptions.RequestException as error:
        print(f"Erro ao conectar ao NetBox: {error}")
        return None


def get_rack_devices(rack_id: int) -> list[NetBoxObject] | None:
    url = f"{NETBOX_URL}/api/dcim/devices/?rack_id={rack_id}"
    return _get_paginated(url)


def get_storage_devices() -> list[NetBoxObject] | None:
    roles = _get_paginated(f"{NETBOX_URL}/api/dcim/device-roles/")
    if roles is None:
        return None
    role_ids = [role["id"] for role in roles if (role.get("name") or "").casefold() in {"controller", "disk array", "storage"}]
    if not role_ids:
        return []
    url = f"{NETBOX_URL}/api/dcim/devices/?{urlencode([('role_id', role_id) for role_id in role_ids])}"
    return _get_paginated(url)


def get_server_devices(limit: int = 15, offset: int = 0, search: str = "", asset_tag: str = "") -> NetBoxObject | None:
    roles = _get_paginated(f"{NETBOX_URL}/api/dcim/device-roles/")
    if roles is None:
        return None
    role_ids = [role["id"] for role in roles
                if {(role.get(key) or "").casefold() for key in ("name", "slug")} & {"server", "servidor"}]
    if not role_ids:
        return {"count": 0, "results": [], "next": None}
    params = [("role_id", role_id) for role_id in role_ids]
    params.extend((("limit", limit), ("offset", offset)))
    if search:
        params.append(("name__ic", search))
    if asset_tag:
        params.append(("asset_tag__ic", asset_tag))
    url = f"{NETBOX_URL}/api/dcim/devices/?{urlencode(params)}"
    return _get_json(url)


def get_ip_addresses() -> list[NetBoxObject] | None:
    return _get_paginated(f"{NETBOX_URL}/api/ipam/ip-addresses/")


def get_prefixes() -> list[NetBoxObject] | None:
    return _get_paginated(f"{NETBOX_URL}/api/ipam/prefixes/")


#informações individuais do servidores ou objetos
def get_device_data(device_id: int) -> NetBoxObject | None:
    
    url = f"{NETBOX_URL}/api/dcim/devices/{device_id}/"
    
    return _get_json(url)

#informações das elevação dos racks
def get_rack_elevation(rack_id: int, face: str = "front") -> list[NetBoxObject] | None:
    
    url = f"{NETBOX_URL}/api/dcim/racks/{rack_id}/elevation/?face={face}"
    
    return _get_paginated(url)

#informações dos racks
def get_rack_data() -> list[NetBoxObject] | None:
    url = f"{NETBOX_URL}/api/dcim/racks/"
    return _get_paginated(url)

#pegar localização ex: ( Cachoeira - Paulista )
def get_locations(site_id: int) -> NetBoxObject | None:
    url = f"{NETBOX_URL}/api/dcim/locations/?site_id={site_id}"
    return _get_json(url)

#pegar site 
def get_sites() -> list[NetBoxObject] | None:
    url = f"{NETBOX_URL}/api/dcim/sites/"
    return _get_paginated(url)

