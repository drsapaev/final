import { useLayoutEffect } from 'react';

export function useDocumentLanguage(language?: string) {
  useLayoutEffect(() => {
    if (!language) return undefined;

    const root = document.documentElement;
    const previousLanguage = root.getAttribute('lang');
    root.lang = language;

    return () => {
      if (root.lang !== language) return;
      if (previousLanguage === null) root.removeAttribute('lang');
      else root.lang = previousLanguage;
    };
  }, [language]);
}
