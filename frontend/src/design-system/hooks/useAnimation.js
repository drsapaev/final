import { useState, useEffect, useCallback, useRef } from 'react';

// Хук для управления анимациями
export const useAnimation = (initialState = false) => {
  const [isAnimating, setIsAnimating] = useState(initialState);
  const [animationProgress, setAnimationProgress] = useState(0);
  const animationRef = useRef(null);

  const startAnimation = useCallback((duration = 300, easing = 'ease-out') => {
    setIsAnimating(true);
    setAnimationProgress(0);
    
    const startTime = performance.now();
    
    const animate = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      
      // Применяем easing функцию
      let easedProgress;
      switch (easing) {
        case 'ease-in':
          easedProgress = progress * progress;
          break;
        case 'ease-out':
          easedProgress = 1 - (1 - progress) * (1 - progress);
          break;
        case 'ease-in-out':
          easedProgress = progress < 0.5 
            ? 2 * progress * progress 
            : 1 - 2 * (1 - progress) * (1 - progress);
          break;
        case 'linear':
          easedProgress = progress;
          break;
        default:
          easedProgress = progress;
      }
      
      setAnimationProgress(easedProgress);
      
      if (progress < 1) {
        animationRef.current = requestAnimationFrame(animate);
      } else {
        setIsAnimating(false);
      }
    };
    
    animationRef.current = requestAnimationFrame(animate);
  }, []);

  const stopAnimation = useCallback(() => {
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
      setIsAnimating(false);
    }
  }, []);

  useEffect(() => {
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, []);

  return {
    isAnimating,
    animationProgress,
    startAnimation,
    stopAnimation
  };
};

// Хук для stagger анимаций (последовательные анимации)
export const useStagger = (items, delay = 100) => {
  const [animatedItems, setAnimatedItems] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);

  const startStaggerAnimation = useCallback(() => {
    setCurrentIndex(0);
    setAnimatedItems([]);
    
    const animateNext = (index) => {
      if (index >= items.length) return;
      
      setAnimatedItems(prev => [...prev, items[index]]);
      setCurrentIndex(index + 1);
      
      setTimeout(() => {
        animateNext(index + 1);
      }, delay);
    };
    
    animateNext(0);
  }, [items, delay]);

  const resetStagger = useCallback(() => {
    setAnimatedItems([]);
    setCurrentIndex(0);
  }, []);

  return {
    animatedItems,
    currentIndex,
    startStaggerAnimation,
    resetStagger,
    isComplete: currentIndex >= items.length
  };
};

// Хук для progress анимации
export const useProgress = (initialProgress = 0) => {
  const [progress, setProgress] = useState(initialProgress);
  const [isAnimating, setIsAnimating] = useState(false);
  const progressRef = useRef(null);

  const animateProgress = useCallback((targetProgress, duration = 1000) => {
    setIsAnimating(true);
    const startProgress = progress;
    const startTime = performance.now();
    
    const animate = (currentTime) => {
      const elapsed = currentTime - startTime;
      const currentProgress = Math.min(elapsed / duration, 1);
      
      const newProgress = startProgress + (targetProgress - startProgress) * currentProgress;
      setProgress(newProgress);
      
      if (currentProgress < 1) {
        progressRef.current = requestAnimationFrame(animate);
      } else {
        setIsAnimating(false);
      }
    };
    
    progressRef.current = requestAnimationFrame(animate);
  }, [progress]);

  const setProgressImmediate = useCallback((value) => {
    setProgress(value);
  }, []);

  useEffect(() => {
    return () => {
      if (progressRef.current) {
        cancelAnimationFrame(progressRef.current);
      }
    };
  }, []);

  return {
    progress,
    isAnimating,
    animateProgress,
    setProgressImmediate
  };
};

// Хук для fade анимации
export const useFade = (initialVisible = false) => {
  const [isVisible, setIsVisible] = useState(initialVisible);
  const [opacity, setOpacity] = useState(initialVisible ? 1 : 0);
  const fadeRef = useRef(null);

  const fadeIn = useCallback((duration = 300) => {
    setIsVisible(true);
    setOpacity(0);
    
    const startTime = performance.now();
    
    const animate = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      
      setOpacity(progress);
      
      if (progress < 1) {
        fadeRef.current = requestAnimationFrame(animate);
      }
    };
    
    fadeRef.current = requestAnimationFrame(animate);
  }, []);

  const fadeOut = useCallback((duration = 300) => {
    const startTime = performance.now();
    
    const animate = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      
      setOpacity(1 - progress);
      
      if (progress < 1) {
        fadeRef.current = requestAnimationFrame(animate);
      } else {
        setIsVisible(false);
      }
    };
    
    fadeRef.current = requestAnimationFrame(animate);
  }, []);

  useEffect(() => {
    return () => {
      if (fadeRef.current) {
        cancelAnimationFrame(fadeRef.current);
      }
    };
  }, []);

  return {
    isVisible,
    opacity,
    fadeIn,
    fadeOut
  };
};

// Хук для slide анимации
export const useSlide = (initialVisible = false, direction = 'up') => {
  const [isVisible, setIsVisible] = useState(initialVisible);
  const [transform, setTransform] = useState(initialVisible ? 'translateY(0)' : 'translateY(20px)');
  const slideRef = useRef(null);

  const slideIn = useCallback((duration = 300) => {
    setIsVisible(true);
    
    let initialTransform;
    switch (direction) {
      case 'up':
        initialTransform = 'translateY(20px)';
        break;
      case 'down':
        initialTransform = 'translateY(-20px)';
        break;
      case 'left':
        initialTransform = 'translateX(20px)';
        break;
      case 'right':
        initialTransform = 'translateX(-20px)';
        break;
      default:
        initialTransform = 'translateY(20px)';
    }
    
    setTransform(initialTransform);
    
    const startTime = performance.now();
    
    const animate = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      
      const easedProgress = 1 - (1 - progress) * (1 - progress); // ease-out
      
      let newTransform;
      switch (direction) {
        case 'up':
          newTransform = `translateY(${20 * (1 - easedProgress)}px)`;
          break;
        case 'down':
          newTransform = `translateY(${-20 * (1 - easedProgress)}px)`;
          break;
        case 'left':
          newTransform = `translateX(${20 * (1 - easedProgress)}px)`;
          break;
        case 'right':
          newTransform = `translateX(${-20 * (1 - easedProgress)}px)`;
          break;
        default:
          newTransform = `translateY(${20 * (1 - easedProgress)}px)`;
      }
      
      setTransform(newTransform);
      
      if (progress < 1) {
        slideRef.current = requestAnimationFrame(animate);
      }
    };
    
    slideRef.current = requestAnimationFrame(animate);
  }, [direction]);

  const slideOut = useCallback((duration = 300) => {
    const startTime = performance.now();
    
    const animate = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      
      const easedProgress = progress * progress; // ease-in
      
      let newTransform;
      switch (direction) {
        case 'up':
          newTransform = `translateY(${20 * easedProgress}px)`;
          break;
        case 'down':
          newTransform = `translateY(${-20 * easedProgress}px)`;
          break;
        case 'left':
          newTransform = `translateX(${20 * easedProgress}px)`;
          break;
        case 'right':
          newTransform = `translateX(${-20 * easedProgress}px)`;
          break;
        default:
          newTransform = `translateY(${20 * easedProgress}px)`;
      }
      
      setTransform(newTransform);
      
      if (progress < 1) {
        slideRef.current = requestAnimationFrame(animate);
      } else {
        setIsVisible(false);
      }
    };
    
    slideRef.current = requestAnimationFrame(animate);
  }, [direction]);

  useEffect(() => {
    return () => {
      if (slideRef.current) {
        cancelAnimationFrame(slideRef.current);
      }
    };
  }, []);

  return {
    isVisible,
    transform,
    slideIn,
    slideOut
  };
};

// Хук для scale анимации
export const useScale = (initialVisible = false) => {
  const [isVisible, setIsVisible] = useState(initialVisible);
  const [scale, setScale] = useState(initialVisible ? 1 : 0.9);
  const scaleRef = useRef(null);

  const scaleIn = useCallback((duration = 300) => {
    setIsVisible(true);
    setScale(0.9);
    
    const startTime = performance.now();
    
    const animate = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      
      const easedProgress = 1 - (1 - progress) * (1 - progress); // ease-out
      const newScale = 0.9 + (1 - 0.9) * easedProgress;
      
      setScale(newScale);
      
      if (progress < 1) {
        scaleRef.current = requestAnimationFrame(animate);
      }
    };
    
    scaleRef.current = requestAnimationFrame(animate);
  }, []);

  const scaleOut = useCallback((duration = 300) => {
    const startTime = performance.now();
    
    const animate = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      
      const easedProgress = progress * progress; // ease-in
      const newScale = 1 - (1 - 0.9) * easedProgress;
      
      setScale(newScale);
      
      if (progress < 1) {
        scaleRef.current = requestAnimationFrame(animate);
      } else {
        setIsVisible(false);
      }
    };
    
    scaleRef.current = requestAnimationFrame(animate);
  }, []);

  useEffect(() => {
    return () => {
      if (scaleRef.current) {
        cancelAnimationFrame(scaleRef.current);
      }
    };
  }, []);

  return {
    isVisible,
    scale,
    scaleIn,
    scaleOut
  };
};
