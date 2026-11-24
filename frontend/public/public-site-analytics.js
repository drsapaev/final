(() => {
  const tagName = 'kosmed-public-site-analytics';
  const path = '/api/v1/public-site/analytics/events';

  function getEndpoint(value) {
    try {
      const url = new URL(value);
      const isLocalHttp = url.protocol === 'http:'
        && (url.hostname === 'localhost' || url.hostname === '127.0.0.1');
      if ((url.protocol === 'https:' || isLocalHttp) && url.href === url.origin + path) return url.href;
    } catch {
      // Invalid configuration leaves collection disabled.
    }
    return undefined;
  }

  function sendEvent(endpoint, event) {
    void fetch(endpoint, {
      method: 'POST',
      body: event,
      headers: { 'Content-Type': 'text/plain' },
      credentials: 'omit',
      referrerPolicy: 'no-referrer',
      redirect: 'error',
      keepalive: true,
      cache: 'no-store',
    }).catch(() => {
      // Analytics does not affect navigation or the booking form.
    });
  }

  function install() {
    if (customElements.get(tagName)) return;

    class PublicSiteAnalytics extends HTMLElement {
      static observedAttributes = ['data-event'];
      #endpoint;
      #reported = false;
      #phoneListener;

      connectedCallback() {
        this.#endpoint = getEndpoint(this.getAttribute('data-endpoint'));
        if (!this.#endpoint) return;
        this.#reportView();
        if (!this.hasAttribute('data-track-phone')) return;
        const scope = this.closest('.public-site');
        if (!scope) return;
        this.#phoneListener = new AbortController();
        scope.addEventListener('click', this.#onPhoneClick, { signal: this.#phoneListener.signal });
      }

      disconnectedCallback() {
        this.#phoneListener?.abort();
      }

      attributeChangedCallback() {
        if (this.isConnected) this.#reportView();
      }

      #reportView() {
        if (!this.#endpoint || this.#reported) return;
        const event = this.getAttribute('data-event');
        if (event !== 'site_view' && event !== 'booking_form_open') return;
        this.#reported = true;
        sendEvent(this.#endpoint, event);
      }

      #onPhoneClick = (event) => {
        if (event.target instanceof Element && event.target.closest('a[href^="tel:" i]')) {
          sendEvent(this.#endpoint, 'phone_click');
        }
      };
    }

    customElements.define(tagName, PublicSiteAnalytics);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else {
    install();
  }
})();
