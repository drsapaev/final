import { useLayoutEffect } from 'react';

export function useDocumentTitle(title?: string) {
  useLayoutEffect(() => {
    if (!title) return undefined;

    const previousTitle = document.title;
    document.title = title;
    const appliedTitle = document.title;

    return () => {
      if (document.title === appliedTitle) document.title = previousTitle;
    };
  }, [title]);
}
