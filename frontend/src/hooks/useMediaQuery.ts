import { useEffect, useState } from 'react';

/**
 * Хук для проверки медиа-запросов.
 * SSR-safe: на сервере возвращает false (window недоступен).
 */
export const useMediaQuery = (query: string): boolean => {
  const [matches, setMatches] = useState<boolean>(() =>
    typeof window !== 'undefined' ? window.matchMedia(query).matches : false,
  );

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const media = window.matchMedia(query);
    setMatches(media.matches);

    const listener = (): void => setMatches(media.matches);

    // Современные браузеры
    if (media.addEventListener) {
      media.addEventListener('change', listener);
      return () => media.removeEventListener('change', listener);
    }
    // Старые браузеры (Safari < 14)
    media.addListener(listener);
    return () => media.removeListener(listener);
  }, [query]);

  return matches;
};

export type Breakpoint = 'mobile' | 'tablet' | 'desktop' | 'large';

export interface BreakpointState {
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;
  isLargeDesktop: boolean;
  current: Breakpoint;
}

/** Хук для определения breakpoint'ов */
export const useBreakpoint = (): BreakpointState => {
  const isMobile = useMediaQuery('(max-width: 768px)');
  const isTablet = useMediaQuery('(min-width: 769px) and (max-width: 1024px)');
  const isDesktop = useMediaQuery('(min-width: 1025px)');
  const isLargeDesktop = useMediaQuery('(min-width: 1440px)');

  return {
    isMobile,
    isTablet,
    isDesktop,
    isLargeDesktop,
    current: isMobile ? 'mobile' : isTablet ? 'tablet' : isDesktop ? 'desktop' : 'large',
  };
};

export type Orientation = 'portrait' | 'landscape';

/** Хук для определения ориентации */
export const useOrientation = (): Orientation => {
  const [orientation, setOrientation] = useState<Orientation>(() =>
    typeof window !== 'undefined' && window.innerHeight > window.innerWidth
      ? 'portrait'
      : 'landscape',
  );

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handleResize = (): void => {
      setOrientation(
        window.innerHeight > window.innerWidth ? 'portrait' : 'landscape',
      );
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return orientation;
};

/** Хук для определения touch-устройства */
export const useTouchDevice = (): boolean => {
  const [isTouch, setIsTouch] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const nav = navigator as Navigator & { msMaxTouchPoints?: number };
    setIsTouch(
      'ontouchstart' in window ||
        nav.maxTouchPoints > 0 ||
        (nav.msMaxTouchPoints ?? 0) > 0,
    );
  }, []);

  return isTouch;
};

// Default export for compatibility with modules importing the hook as default
export default useMediaQuery;
