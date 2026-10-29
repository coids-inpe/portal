from apps.infra.utils.netbox import get_rack_data, get_rack_elevation


class RackVisualizationService:
    
    """Prepara os racks do NetBox para a página de ocupação frontal."""

    def build_page(self, search_query="", selected_group="", offset=0, page_size=12):       
        # Estas chaves são usadas pelo template, mesmo quando o NetBox falha.
        page = {
            "racks": [],
            "groups": [],
            "total_racks": 0,
            "next_offset": None,
            "search_query": search_query.strip(),
            "selected_group": selected_group,
        }

        racks_from_netbox = get_rack_data()
       
        if racks_from_netbox is None:
            page["netbox_error"] = True
            return page
       
        page["netbox_error"] = False

        # Monta as opções do filtro com os grupos presentes nos racks recebidos.
        groups_by_id = {}
        
        for rack in racks_from_netbox:
            group = rack.get("group")
        
            if group:
                group_id = str(group["id"])
                groups_by_id[group_id] = {"id": group_id, "name": group["name"]}

        
        groups = list(groups_by_id.values())
        
        page["groups"] = sorted(
            groups, key=lambda group: group["name"].casefold()
        )

        # O total é calculado depois da busca e do filtro por grupo.
        filtered_racks = self._filter_racks(
            racks_from_netbox, page["search_query"], selected_group
        )
        
        page["total_racks"] = len(filtered_racks)

        # Offset inválido volta ao início; valores negativos não voltam do fim.
        try:
            offset = max(0, int(offset))
        except ValueError:
            offset = 0


        # Consulta a elevação apenas dos racks desta página.
        batch = filtered_racks[offset:offset + page_size]

        next_offset = offset + len(batch)

        if next_offset < len(filtered_racks):
            page["next_offset"] = next_offset

        for rack in batch:
            card = self.build_card(rack)
            if card["occupied_units"] is None:
                page["netbox_error"] = True
                return page
            page["racks"].append(card)

        return page

    
    def _filter_racks(self, racks, search_query, selected_group):
      
        """
        Retorna só os racks cujo nome contém a busca e cujo grupo foi selecionado.

        Se busca ou grupo estiver vazio, esse filtro não restringe a lista.
        """
        
        normalized_query = search_query.casefold()
        
        filtered_racks = []

        for rack in racks:
            rack_name = rack.get("name") or rack.get("display") or ""
        
            group_id = (rack.get("group") or {}).get("id")

            name_matches = not normalized_query or normalized_query in rack_name.casefold()
        
            group_matches = not selected_group or str(group_id) == selected_group

            
            if not name_matches:
                continue
            if not group_matches:
                continue

            filtered_racks.append(rack)

        return filtered_racks

    
    def build_card(self, rack):
        
        height = rack.get("u_height") or 0
        
        front_units = get_rack_elevation(rack["id"], "front")
        
        occupied_units = None
        
        slots = []

        if front_units is not None:
            occupied_positions = set()
            for unit in front_units:
                if unit.get("occupied"):
                    occupied_positions.add(unit["id"])

            occupied_units = 0

            starting_unit = rack.get("starting_unit", 1)
            highest_unit = starting_unit + height - 1

            for number in range(highest_unit, starting_unit - 1, -1):
                # O NetBox pode identificar a mesma U por N ou N+0.5.
                position_occupied = (
                    number in occupied_positions
                    or number + 0.5 in occupied_positions
                )

                if position_occupied:
                    position_status = "full"
                    occupied_units += 1
                else:
                    position_status = "free"

                slots.append({"number": number, "front": position_status})

        if occupied_units is not None and height:
            occupancy_percent = round(occupied_units / height * 100)
        
        else:
            occupancy_percent = None

        site = rack.get("site") or {}
        location = rack.get("location") or {}
        group = rack.get("group") or {}
        status = rack.get("status") or {}

        return {
            "id": rack["id"],
            "name": rack.get("name") or rack.get("display"),
            "site": site.get("name", "—"),
            "location": location.get("name", "—"),
            "group": group.get("name", "—"),
            "status": status.get("label", "—"),
            "height": height,
            "device_count": rack.get("device_count", 0),
            "occupied_units": occupied_units,
            "occupancy_percent": occupancy_percent,
            "slots": slots,
            "description": rack.get("description", ""),
        }
