(() => {
  function setup(root) {
    if (root.dataset.ready || root.closest('.empty-form')) return;
    root.dataset.ready = 'true';
    const select = root.querySelector('select');
    const input = root.querySelector('.netbox-device-query');
    const find = root.querySelector('.netbox-device-find');
    const more = root.querySelector('.netbox-device-more');
    const status = root.querySelector('.netbox-device-status');
    let offset = 0;
    let query = '';
    async function search(append = false) {
      find.disabled = more.disabled = true;
      status.textContent = 'Consultando o NetBox…';
      const nextQuery = append ? query : input.value.trim();
      const nextOffset = append ? offset : 0;
      try {
        const url = new URL(root.dataset.searchUrl, window.location.origin);
        url.searchParams.set('q', nextQuery);
        url.searchParams.set('offset', nextOffset);
        const response = await fetch(url, {headers: {'Accept': 'application/json'}, redirect: 'error'});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Não foi possível buscar equipamentos.');
        if (!append) {
          // Preserve the selected device when the next search returns different results.
          for (const option of Array.from(select.options)) {
            if (option.value && !option.selected) option.remove();
          }
        }
        for (const device of data.results) {
          const existing = Array.from(select.options).find(option => option.value === String(device.id));
          if (existing) existing.textContent = device.label;
          else select.add(new Option(device.label, String(device.id)));
        }
        // The portal theme wraps selects with bootstrap-select; refresh its visible list.
        const jquery = window.jQuery;
        if (jquery && jquery.fn.selectpicker && jquery(select).data('selectpicker')) {
          jquery(select).selectpicker('refresh');
        }
        query = nextQuery;
        offset = nextOffset + data.results.length;
        more.hidden = !data.more;
        status.textContent = data.results.length
          ? `${data.results.length} equipamento(s) carregado(s). Selecione na lista.`
          : 'Nenhum equipamento encontrado. A seleção anterior foi mantida.';
      } catch (error) {
        status.textContent = error.message || 'Falha ao consultar o NetBox. Tente novamente.';
      } finally {
        find.disabled = more.disabled = false;
      }
    }
    find.addEventListener('click', () => search());
    more.addEventListener('click', () => search(true));
    input.addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        if (!find.disabled) search();
      }
    });
    select.addEventListener('change', () => { status.textContent = select.value ? 'Equipamento selecionado.' : ''; });
  }
  function scan(scope = document) {
    scope.querySelectorAll('.netbox-device-picker').forEach(setup);
  }
  function start() {
    scan();
    new MutationObserver(() => scan()).observe(document.body, {childList: true, subtree: true});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
