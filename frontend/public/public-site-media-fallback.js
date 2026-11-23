(() => {
  const selector = '.public-site img[data-public-site-image]';

  document.addEventListener('error', ({ target }) => {
    if (target instanceof HTMLImageElement && target.matches(selector)) {
      target.dataset.publicSiteImage = 'unavailable';
    }
  }, true);

  // The asynchronous script can arrive after the browser has reported an error.
  const detectCompletedFailures = () => {
    document.querySelectorAll(selector).forEach((image) => {
      if (image.complete && image.naturalWidth === 0) {
        image.dataset.publicSiteImage = 'unavailable';
      }
    });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', detectCompletedFailures, { once: true });
  } else {
    detectCompletedFailures();
  }
})();
