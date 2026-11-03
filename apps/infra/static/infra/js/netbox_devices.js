(() => {
  const grid = document.getElementById("netbox-rack-grid");
  const dialog = document.getElementById("netbox-device-dialog");
  if (!grid || !dialog) return;
  const title = document.getElementById("netbox-device-title");
  const content = document.getElementById("netbox-device-content");
  const back = document.getElementById("netbox-device-back");
  let activeCard;
  let devicesUrl;

  function message(value) {
    content.replaceChildren();
    const p = document.createElement("p");
    p.textContent = value;
    content.append(p);
  }

  async function getJson(url) {
    const response = await fetch(url, { credentials: "same-origin" });
    if (!response.ok) throw new Error("NetBox indisponível");
    return response.json();
  }

  async function showDevices() {
    back.hidden = true;
    title.textContent = `Dispositivos do rack ${activeCard.querySelector("h2").textContent}`;
    message("Carregando dispositivos...");
    try {
      const { devices } = await getJson(devicesUrl);
      if (!devices.length) return message("Nenhum dispositivo neste rack.");
      content.replaceChildren();
      const list = document.createElement("div");
      list.className = "netbox-device-list";
      devices.forEach((device) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "netbox-device-item";
        button.textContent = `${device.name} · ${device.role} · ${device.status} · ${device.position}`;
        button.addEventListener("click", () => showDevice(device.id));
        list.append(button);
      });
      content.append(list);
    } catch (_) {
      message("Não foi possível consultar os dispositivos. Tente novamente.");
    }
  }

  async function showDevice(id) {
    back.hidden = false;
    message("Carregando informações...");
    try {
      const { device } = await getJson(`${devicesUrl}${id}/`);
      title.textContent = device.name;
      content.replaceChildren();
      const details = document.createElement("dl");
      details.className = "netbox-device-details";
      const fields = {
        status: "Status",
        role: "Função",
        manufacturer: "Fabricante",
        model: "Modelo",
        serial: "Número de série",
        asset_tag: "Patrimônio",
        position: "Posição",
        face: "Face",
        ip: "IP principal",
        description: "Descrição",
      };
      Object.entries(fields).forEach(([key, label]) => {
        const dt = document.createElement("dt");
        const dd = document.createElement("dd");
        dt.textContent = label;
        dd.textContent = device[key];
        details.append(dt, dd);
      });
      content.append(details);
    } catch (_) {
      message("Não foi possível consultar este dispositivo. Tente novamente.");
    }
  }

  function openCard(card) {
    activeCard = card;
    devicesUrl = card.dataset.devicesUrl;
    dialog.showModal();
    showDevices();
  }

  grid.addEventListener("click", (event) => {
    const card = event.target.closest(".netbox-rack-card");
    if (card) openCard(card);
  });
  grid.addEventListener("keydown", (event) => {
    if (
      (event.key === "Enter" || event.key === " ") &&
      event.target.matches(".netbox-rack-card")
    ) {
      event.preventDefault();
      openCard(event.target);
    }
  });
  document
    .getElementById("netbox-device-close")
    .addEventListener("click", () => dialog.close());
  back.addEventListener("click", showDevices);
  dialog.addEventListener("close", () => activeCard?.focus());
})();
