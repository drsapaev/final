// @ts-nocheck — Phase 2: file converted .js → .ts but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

/**
 * UI animation hooks — R-14 / P-009 (UX audit).
 *
 * These hooks were previously in components/ui/native/hooks.js, which had
 * syntax errors (missing `[` in `const [matches, setMatches]`) and was
 * therefore broken in production. The native/ UI kit is being removed in
 * favour of the macOS-like kit (components/ui/macos/). The animation hooks
 * have no equivalent in macos/, so they are moved here to a single
 * canonical location under hooks/.
 *
 * Used by: a handful of admin/analytics components for enter/exit transitions
 * (note: the former admin/KPICard and admin/AdminNavigation consumers were
 * removed as dead code — replaced by MacOSStatCard and the data-driven sidebar
 * respectively). The hooks are
 * intentionally lightweight (no animation library) — they toggle inline
 * styles via state, which is enough for the current usage. If richer
 * animations are needed later, migrate to framer-motion or CSS @keyframes.
 */

import { useState, useEffect } from 'react';

/**
 * Detect the current responsive breakpoint.
 * Returns { isMobile, isTablet, isDesktop, isLargeDesktop, current }.
 */
export const useBreakpoint = () => {
  const [isMobile, setIsMobile] = useState(false);
  const [isTablet, setIsTablet] = useState(false);
  const [isDesktop, setIsDesktop] = useState(false);
  const [isLargeDesktop, setIsLargeDesktop] = useState(false);

  useEffect(() => {
    const update = () => {
      setIsMobile(window.matchMedia('(max-width: 768px)').matches);
      setIsTablet(
        window.matchMedia('(min-width: 769px) and (max-width: 1024px)').matches
      );
      setIsDesktop(
        window.matchMedia('(min-width: 1025px) and (max-width: 1439px)').matches
      );
      setIsLargeDesktop(window.matchMedia('(min-width: 1440px)').matches);
    };

    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  const current = isMobile
    ? 'mobile'
    : isTablet
      ? 'tablet'
      : isDesktop
        ? 'desktop'
        : 'large';

  return { isMobile, isTablet, isDesktop, isLargeDesktop, current };
};

/**
 * Detect whether the current device supports touch input.
 */
export const useTouchDevice = () => {
  const [isTouch, setIsTouch] = useState(false);

  useEffect(() => {
    setIsTouch(
      'ontouchstart' in window ||
        navigator.maxTouchPoints > 0 ||
        navigator.msMaxTouchPoints > 0
    );
  }, []);

  return isTouch;
};

/**
 * Fade in/out animation hook.
 * Returns { isVisible, opacity, fadeIn, fadeOut, toggle, style }.
 */
export const useFade = (initialState = false) => {
  const [isVisible, setIsVisible] = useState(initialState);
  const [opacity, setOpacity] = useState(initialState ? 1 : 0);

  const fadeIn = () => {
    setIsVisible(true);
    setOpacity(1);
  };

  const fadeOut = () => {
    setOpacity(0);
    setTimeout(() => setIsVisible(false), 300);
  };

  const toggle = () => {
    if (isVisible) {
      fadeOut();
    } else {
      fadeIn();
    }
  };

  return {
    isVisible,
    opacity,
    fadeIn,
    fadeOut,
    toggle,
    style: {
      opacity,
      transition: 'opacity 0.3s ease-in-out',
      display: isVisible ? 'block' : 'none',
    },
  };
};

/**
 * Slide in/out animation hook.
 * direction: 'left' (slide from left) or 'right' (slide from right) or 'up' (slide from bottom).
 * Returns { isVisible, transform, slideIn, slideOut, toggle, style }.
 */
export const useSlide = (direction = 'left', initialState = false) => {
  const [isVisible, setIsVisible] = useState(initialState);
  const [transform, setTransform] = useState(
    initialState
      ? 'translateX(0)'
      : direction === 'up'
        ? 'translateY(100%)'
        : `translateX(${direction === 'left' ? '-100%' : '100%'})`
  );

  const slideIn = () => {
    setIsVisible(true);
    setTransform(direction === 'up' ? 'translateY(0)' : 'translateX(0)');
  };

  const slideOut = () => {
    setTransform(
      direction === 'up'
        ? 'translateY(100%)'
        : `translateX(${direction === 'left' ? '-100%' : '100%'})`
    );
    setTimeout(() => setIsVisible(false), 300);
  };

  const toggle = () => {
    if (isVisible) {
      slideOut();
    } else {
      slideIn();
    }
  };

  return {
    isVisible,
    transform,
    slideIn,
    slideOut,
    toggle,
    style: {
      transform,
      transition: 'transform 0.3s ease-in-out',
      display: isVisible ? 'block' : 'none',
    },
  };
};

/**
 * Scale in/out animation hook.
 * Returns { isVisible, scale, scaleIn, scaleOut, toggle, style }.
 */
export const useScale = (initialState = false) => {
  const [isVisible, setIsVisible] = useState(initialState);
  const [scale, setScale] = useState(initialState ? 1 : 0);

  const scaleIn = () => {
    setIsVisible(true);
    setScale(1);
  };

  const scaleOut = () => {
    setScale(0);
    setTimeout(() => setIsVisible(false), 300);
  };

  const toggle = () => {
    if (isVisible) {
      scaleOut();
    } else {
      scaleIn();
    }
  };

  return {
    isVisible,
    scale,
    scaleIn,
    scaleOut,
    toggle,
    style: {
      transform: `scale(${scale})`,
      transition: 'transform 0.3s ease-in-out',
      display: isVisible ? 'block' : 'none',
    },
  };
};

/**
 * Fade-in-on-mount hook.
 * Returns { isVisible, style }.
 */
export const useFadeIn = (delay = 0) => {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(true);
    }, delay);

    return () => clearTimeout(timer);
  }, [delay]);

  return {
    isVisible,
    style: {
      opacity: isVisible ? 1 : 0,
      transition: `opacity 0.3s ease-in-out ${delay}ms`,
    },
  };
};
