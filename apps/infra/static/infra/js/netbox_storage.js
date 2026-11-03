(() => {
  const grid = document.querySelector(".netbox-storage-grid");
  const dialog = document.getElementById("netbox-storage-dialog");
  if (!grid || !dialog) return;

  const title = document.getElementById("netbox-storage-dialog-title");
  const content = document.getElementById("netbox-storage-dialog-content");
  const close = document.getElementById("netbox-storage-dialog-close");
  let trigger = null;

  function message(value) {
    const paragraph = document.createElement("p");
    paragraph.textContent = value;
    content.replaceChildren(paragraph);
  }

  function showDevice(device) {
    title.textContent = device.name;
    const facts = document.createElement("dl");
    facts.className = "netbox-storage-detail-facts";
    const fields = [
      ["Função", device.role],
      ["Status", device.status],
      ["Fabricante", device.manufacturer],
      ["Modelo", device.model],
      ["Site", device.site],
      ["Rack", device.rack],
      ["Posição", device.position == null ? "—" : `U${device.position}`],
      ["Número de série", device.serial],
      ["Patrimônio", device.asset_tag],
      ["IP principal", device.primary_ip],
      ["Descrição", device.description],
    ];
    for (const [label, value] of fields) {
      const term = document.createElement("dt");
      term.textContent = label;
      const definition = document.createElement("dd");
      definition.textContent = value ?? "—";
      facts.append(term, definition);
    }
    content.replaceChildren(facts);
  }

  grid.addEventListener("click", async (event) => {
    const card = event.target.closest("[data-detail-url]");
    if (!card) return;
    trigger = card;
    title.textContent = "Informações do dispositivo";
    message("Carregando informações...");
    dialog.showModal();
    try {
      const response = await fetch(card.dataset.detailUrl, {
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error("NetBox indisponível");
      showDevice((await response.json()).device);
    } catch {
      message("Não foi possível consultar o dispositivo. Tente novamente.");
    }
  });

  close.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => trigger?.focus());
})();
