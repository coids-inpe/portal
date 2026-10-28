import os
import requests

NETBOX_URL = os.getenv("NETBOX_URL")
NETBOX_TOKEN = os.getenv("NETBOX_TOKEN")


def _headers():
    if NETBOX_TOKEN and NETBOX_TOKEN.startswith("nbt_"):
        authentication_type = "Bearer"
    else:
        authentication_type = "Token"

    return {
        "Authorization": f"{authentication_type} {NETBOX_TOKEN}",
        "Accept": "application/json",
    }


def _get_paginated(url):
    results = []
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
    

def _get_json(url):

    try:
        response = requests.get(url, headers=_headers(), timeout=5)

        response.raise_for_status()
        
        return response.json()
    
    except requests.exceptions.RequestException as error:
        print(f"Erro ao conectar ao NetBox: {error}")
        return None


#informações individuais do servidores ou objetos
def get_device_data(device_id):
    
    url = f"{NETBOX_URL}/api/dcim/devices/{device_id}/"
    
    return _get_json(url)

#informações das elevação dos racks
def get_rack_elevation(rack_id, face="front"):
    
    url = f"{NETBOX_URL}/api/dcim/racks/{rack_id}/elevation/?face={face}"
    
    return _get_paginated(url)

#informações dos racks
def get_rack_data():
    url = f"{NETBOX_URL}/api/dcim/racks/"
    return _get_paginated(url)

#pegar localização ex: ( Cachoeira - Paulista )
def get_locations(site_id):
    url = f"{NETBOX_URL}/api/dcim/locations/?site_id={site_id}"
    return _get_json(url)

#pegar site 
def get_sites():
    url = f"{NETBOX_URL}/api/dcim/sites/"
    return _get_json(url)

