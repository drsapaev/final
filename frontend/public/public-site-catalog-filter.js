(() => {
  const tagName = 'public-site-catalog-filter';

  function normalize(value) {
    return value.normalize('NFC')
      .toLowerCase()
      .replace(/ё/g, 'е')
      .replace(/[‘’ʻʼ`]/g, '\'');
  }

  class PublicSiteCatalogFilter extends HTMLElement {
    #cleanup;

    connectedCallback() {
      if (this.#cleanup) return;

      const controls = this.querySelector('[data-catalog-controls]');
      const search = controls?.querySelector('input[type="search"]');
      const select = controls?.querySelector('select');
      const reset = controls?.querySelector('[data-catalog-reset]');
      const count = this.querySelector('[data-catalog-count]');
      const empty = this.querySelector('[data-catalog-empty]');
      if (!controls || !search || !reset || !count || !empty) return;

      const rows = Array.from(this.querySelectorAll('[data-catalog-item]'), (element) => {
        const name = element.querySelector('.public-site__list-title')?.textContent ?? '';
        const group = element.dataset.catalogGroup ?? '';
        return { element, group, text: normalize(`${name} ${group}`) };
      });
      const listeners = new AbortController();
      let announcementTimer;

      function applyFilters(announceImmediately = false) {
        const terms = normalize(search.value).match(/\S+/g) ?? [];
        const selectedGroup = select?.value ?? '';
        let visibleCount = 0;

        for (const { element, group, text } of rows) {
          const matches = (!selectedGroup || group === selectedGroup)
            && terms.every((term) => text.includes(term));
          element.hidden = !matches;
          if (matches) visibleCount += 1;
        }

        empty.hidden = visibleCount !== 0;
        clearTimeout(announcementTimer);
        const nextCount = String(visibleCount);
        if (count.textContent === nextCount) return;
        if (announceImmediately) {
          count.textContent = nextCount;
        } else {
          announcementTimer = setTimeout(() => { count.textContent = nextCount; }, 160);
        }
      }

      const listenerOptions = { signal: listeners.signal };
      search.addEventListener('input', () => applyFilters(), listenerOptions);
      select?.addEventListener('change', () => applyFilters(), listenerOptions);
      reset.addEventListener('click', () => {
        search.value = '';
        if (select) select.value = '';
        applyFilters();
        search.focus();
      }, listenerOptions);

      this.#cleanup = () => {
        listeners.abort();
        clearTimeout(announcementTimer);
      };
      applyFilters(true);
      controls.hidden = false;
    }

    disconnectedCallback() {
      this.#cleanup?.();
      this.#cleanup = undefined;
    }
  }

  function register() {
    if (!customElements.get(tagName)) customElements.define(tagName, PublicSiteCatalogFilter);
  }

  // Let the parser finish before upgrading server-rendered catalogs.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', register, { once: true });
  } else {
    register();
  }
})();
