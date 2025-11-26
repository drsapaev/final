/**
 * Улучшенная система адаптивности для медицинских интерфейсов
 * Основана на принципах mobile-first и медицинских стандартах UX
 */

import { useState, useEffect } from 'react';

// Хук для определения размера экрана
export const useBreakpoint = () => {
  const [breakpoint, setBreakpoint] = useState(() => {
    if (typeof window === 'undefined') return 'md';
    
    const width = window.innerWidth;
    if (width < 640) return 'xs';
    if (width < 768) return 'sm';
    if (width < 1024) return 'md';
    if (width < 1280) return 'lg';
    if (width < 1536) return 'xl';
    return '2xl';
  });

  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth;
      let newBreakpoint = 'md';
      
      if (width < 640) newBreakpoint = 'xs';
      else if (width < 768) newBreakpoint = 'sm';
      else if (width < 1024) newBreakpoint = 'md';
      else if (width < 1280) newBreakpoint = 'lg';
      else if (width < 1536) newBreakpoint = 'xl';
      else newBreakpoint = '2xl';
      
      setBreakpoint(newBreakpoint);
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
    isDesktop: breakpoint === 'lg' || breakpoint === 'xl' || breakpoint === '2xl'
  };
};

// Хук для определения устройства
export const useDevice = () => {
  const [device, setDevice] = useState(() => {
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
    isDesktop: device === 'desktop'
  };
};

// Хук для определения ориентации экрана
export const useOrientation = () => {
  const [orientation, setOrientation] = useState(() => {
    if (typeof window === 'undefined') return 'landscape';
    return window.innerWidth > window.innerHeight ? 'landscape' : 'portrait';
  });

  useEffect(() => {
    const handleResize = () => {
      setOrientation(window.innerWidth > window.innerHeight ? 'landscape' : 'portrait');
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return {
    orientation,
    isPortrait: orientation === 'portrait',
    isLandscape: orientation === 'landscape'
  };
};

// Хук для определения поддержки touch
export const useTouchDevice = () => {
  const [isTouchDevice, setIsTouchDevice] = useState(() => {
    if (typeof window === 'undefined') return false;
    return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
  });

  return { isTouchDevice };
};

// Хук для определения поддержки hover
export const useHoverSupport = () => {
  const [hasHoverSupport, setHasHoverSupport] = useState(() => {
    if (typeof window === 'undefined') return true;
    return window.matchMedia('(hover: hover)').matches;
  });

  useEffect(() => {
    const mediaQuery = window.matchMedia('(hover: hover)');
    const handleChange = (e) => setHasHoverSupport(e.matches);
    
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  return { hasHoverSupport };
};

// Хук для определения поддержки reduced motion
export const useReducedMotion = () => {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handleChange = (e) => setPrefersReducedMotion(e.matches);
    
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  return { prefersReducedMotion };
};

// Хук для определения поддержки высокого контраста
export const useHighContrast = () => {
  const [prefersHighContrast, setPrefersHighContrast] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-contrast: high)').matches;
  });

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-contrast: high)');
    const handleChange = (e) => setPrefersHighContrast(e.matches);
    
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  return { prefersHighContrast };
};

// Комбинированный хук для всех медиа-запросов
export const useEnhancedMediaQuery = () => {
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
    ...highContrast
  };
};

export default useBreakpoint;
