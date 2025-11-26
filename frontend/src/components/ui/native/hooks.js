import React, { useState, useEffect } from 'react';

/**
 * Нативные хуки для замены дизайн-системы
 * Совместимые с существующим API
 */

// Хук для проверки медиа-запросов
export const useMediaQuery = (query) => {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const media = window.matchMedia(query);
    
    if (media.matches !== matches) {
      setMatches(media.matches);
    }

    const listener = () => setMatches(media.matches);
    
    // Современные браузеры
    if (media.addEventListener) {
      media.addEventListener('change', listener);
      return () => media.removeEventListener('change', listener);
    } else {
      // Старые браузеры
      media.addListener(listener);
      return () => media.removeListener(listener);
    }
  }, [matches, query]);

  return matches;
};

// Хук для определения breakpoint'ов (совместимый с дизайн-системой)
export const useBreakpoint = () => {
  const isMobile = useMediaQuery('(max-width: 768px)');
  const isTablet = useMediaQuery('(min-width: 769px) and (max-width: 1024px)');
  const isDesktop = useMediaQuery('(min-width: 1025px)');
  const isLargeDesktop = useMediaQuery('(min-width: 1440px)');

  return {
    isMobile,
    isTablet,
    isDesktop,
    isLargeDesktop,
    current: isMobile ? 'mobile' : isTablet ? 'tablet' : isDesktop ? 'desktop' : 'large'
  };
};

// Хук для определения touch-устройства (совместимый с дизайн-системой)
export const useTouchDevice = () => {
  const [isTouch, setIsTouch] = useState(false);

  useEffect(() => {
    const checkTouch = () => {
      setIsTouch(
        'ontouchstart' in window ||
        navigator.maxTouchPoints > 0 ||
        navigator.msMaxTouchPoints > 0
      );
    };

    checkTouch();
  }, []);

  return isTouch;
};

// Базовые анимационные хуки (совместимые с дизайн-системой)
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
      display: isVisible ? 'block' : 'none'
    }
  };
};

export const useSlide = (direction = 'left', initialState = false) => {
  const [isVisible, setIsVisible] = useState(initialState);
  const [transform, setTransform] = useState(
    initialState ? 'translateX(0)' : `translateX(${direction === 'left' ? '-100%' : '100%'})`
  );

  const slideIn = () => {
    setIsVisible(true);
    setTransform('translateX(0)');
  };

  const slideOut = () => {
    setTransform(`translateX(${direction === 'left' ? '-100%' : '100%'})`);
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
      display: isVisible ? 'block' : 'none'
    }
  };
};

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
      display: isVisible ? 'block' : 'none'
    }
  };
};

// Дополнительные хуки для анимаций
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
      transition: `opacity 0.3s ease-in-out ${delay}ms`
    }
  };
};

export const useAnimation = (initialState = false) => {
  const [isAnimating, setIsAnimating] = useState(initialState);
  const [animationProgress, setAnimationProgress] = useState(0);

  const startAnimation = () => {
    setIsAnimating(true);
    setAnimationProgress(0);
  };

  const stopAnimation = () => {
    setIsAnimating(false);
    setAnimationProgress(100);
  };

  const updateProgress = (progress) => {
    setAnimationProgress(Math.max(0, Math.min(100, progress)));
  };

  return {
    isAnimating,
    animationProgress,
    startAnimation,
    stopAnimation,
    updateProgress
  };
};

export const useProgress = (duration = 1000) => {
  const [progress, setProgress] = useState(0);
  const [isRunning, setIsRunning] = useState(false);

  const start = () => {
    setIsRunning(true);
    setProgress(0);
    
    const startTime = Date.now();
    const animate = () => {
      const elapsed = Date.now() - startTime;
      const newProgress = Math.min((elapsed / duration) * 100, 100);
      
      setProgress(newProgress);
      
      if (newProgress < 100) {
        requestAnimationFrame(animate);
      } else {
        setIsRunning(false);
      }
    };
    
    requestAnimationFrame(animate);
  };

  const reset = () => {
    setProgress(0);
    setIsRunning(false);
  };

  return {
    progress,
    isRunning,
    start,
    reset
  };
};

export const useStagger = (items = [], delay = 100) => {
  const [visibleItems, setVisibleItems] = useState([]);

  useEffect(() => {
    setVisibleItems([]);
    
    items.forEach((item, index) => {
      setTimeout(() => {
        setVisibleItems(prev => [...prev, item]);
      }, index * delay);
    });
  }, [items, delay]);

  return visibleItems;
};
