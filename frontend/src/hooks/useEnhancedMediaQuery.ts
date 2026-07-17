/**
 * Улучшенная система адаптивности для медицинских интерфейсов.
 * Основана на принципах mobile-first и медицинских стандартах UX.
 */

import { useEffect, useState } from 'react';

export type BreakpointName = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl';
export type DeviceType = 'mobile' | 'tablet' | 'desktop';
export type OrientationType = 'portrait' | 'landscape';

export interface BreakpointInfo {
  breakpoint: BreakpointName;
  isXs: boolean;
  isSm: boolean;
  isMd: boolean;
  isLg: boolean;
  isXl: boolean;
  is2Xl: boolean;
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;
}

export interface DeviceInfo {
  device: DeviceType;
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;
}

export interface OrientationInfo {
  orientation: OrientationType;
  isPortrait: boolean;
  isLandscape: boolean;
}

export interface TouchInfo {
  isTouchDevice: boolean;
}

export interface HoverInfo {
  hasHoverSupport: boolean;
}

export interface ReducedMotionInfo {
  prefersReducedMotion: boolean;
}

export interface HighContrastInfo {
  prefersHighContrast: boolean;
}

export type EnhancedMediaQueryInfo = BreakpointInfo &
  DeviceInfo &
  OrientationInfo &
  TouchInfo &
  HoverInfo &
  ReducedMotionInfo &
  HighContrastInfo;

function resolveBreakpoint(width: number): BreakpointName {
  if (width < 640) return 'xs';
  if (width < 768) return 'sm';
  if (width < 1024) return 'md';
  if (width < 1280) return 'lg';
  if (width < 1536) return 'xl';
  return '2xl';
}

export const useBreakpoint = (): BreakpointInfo => {
  const [breakpoint, setBreakpoint] = useState<BreakpointName>(() => {
    if (typeof window === 'undefined') return 'md';
    return resolveBreakpoint(window.innerWidth);
  });

  useEffect(() => {
    const handleResize = (): void => {
      setBreakpoint(resolveBreakpoint(window.innerWidth));
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return {
    breakpoint,
    isXs: breakpoint === 'xs',
    isSm: breakpoint === 'sm',
    isMd: breakpoint === 'md',
    isLg: breakpoint === 'lg',
    isXl: breakpoint === 'xl',
    is2Xl: breakpoint === '2xl',
    isMobile: breakpoint === 'xs' || breakpoint === 'sm',
    isTablet: breakpoint === 'md',
    isDesktop: breakpoint === 'lg' || breakpoint === 'xl' || breakpoint === '2xl',
  };
};

export const useDevice = (): DeviceInfo => {
  const [device] = useState<DeviceType>(() => {
    if (typeof window === 'undefined') return 'desktop';

    const userAgent = navigator.userAgent.toLowerCase();
    const isMobile = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(userAgent);
    const isTablet = /ipad|android(?!.*mobile)/i.test(userAgent);

    if (isMobile) return 'mobile';
    if (isTablet) return 'tablet';
    return 'desktop';
  });

  return {
    device,
    isMobile: device === 'mobile',
    isTablet: device === 'tablet',
    isDesktop: device === 'desktop',
  };
};

export const useOrientation = (): OrientationInfo => {
  const [orientation, setOrientation] = useState<OrientationType>(() => {
    if (typeof window === 'undefined') return 'landscape';
    return window.innerWidth > window.innerHeight ? 'landscape' : 'portrait';
  });

  useEffect(() => {
    const handleResize = (): void => {
      setOrientation(window.innerWidth > window.innerHeight ? 'landscape' : 'portrait');
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return {
    orientation,
    isPortrait: orientation === 'portrait',
    isLandscape: orientation === 'landscape',
  };
};

export const useTouchDevice = (): TouchInfo => {
  const [isTouchDevice] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
  });

  return { isTouchDevice };
};

export const useHoverSupport = (): HoverInfo => {
  const [hasHoverSupport, setHasHoverSupport] = useState<boolean>(() => {
    if (typeof window === 'undefined') return true;
    return window.matchMedia('(hover: hover)').matches;
  });

  useEffect(() => {
    const mediaQuery = window.matchMedia('(hover: hover)');
    const handleChange = (e: MediaQueryListEvent): void => setHasHoverSupport(e.matches);

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  return { hasHoverSupport };
};

export const useReducedMotion = (): ReducedMotionInfo => {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handleChange = (e: MediaQueryListEvent): void => setPrefersReducedMotion(e.matches);

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  return { prefersReducedMotion };
};

export const useHighContrast = (): HighContrastInfo => {
  const [prefersHighContrast, setPrefersHighContrast] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-contrast: high)').matches;
  });

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-contrast: high)');
    const handleChange = (e: MediaQueryListEvent): void => setPrefersHighContrast(e.matches);

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  return { prefersHighContrast };
};

export const useEnhancedMediaQuery = (): EnhancedMediaQueryInfo => {
  const breakpoint = useBreakpoint();
  const device = useDevice();
  const orientation = useOrientation();
  const touchDevice = useTouchDevice();
  const hoverSupport = useHoverSupport();
  const reducedMotion = useReducedMotion();
  const highContrast = useHighContrast();

  return {
    ...breakpoint,
    ...device,
    ...orientation,
    ...touchDevice,
    ...hoverSupport,
    ...reducedMotion,
    ...highContrast,
  };
};

export default useBreakpoint;
