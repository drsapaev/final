import { useState, useEffect, useRef } from 'react';

// Хук для анимации появления/исчезновения
export const useFadeIn = (duration = 300, delay = 0) => {
  const [isVisible, setIsVisible] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(true);
      setIsAnimating(true);
    }, delay);

    return () => clearTimeout(timer);
  }, [delay]);

  const fadeOut = () => {
    setIsAnimating(false);
    setTimeout(() => setIsVisible(false), duration);
  };

  return {
    isVisible,
    isAnimating,
    fadeOut,
    style: {
      opacity: isAnimating ? 1 : 0,
      transform: isAnimating ? 'translateY(0)' : 'translateY(20px)',
      transition: `all ${duration}ms cubic-bezier(0.4, 0, 0.2, 1)`
    }
  };
};

// Хук для анимации масштабирования
export const useScale = (initialScale = 1, targetScale = 1.05) => {
  const [scale, setScale] = useState(initialScale);

  const scaleIn = () => setScale(targetScale);
  const scaleOut = () => setScale(initialScale);

  return {
    scale,
    scaleIn,
    scaleOut,
    style: {
      transform: `scale(${scale})`,
      transition: 'transform 0.2s cubic-bezier(0.4, 0, 0.2, 1)'
    }
  };
};

// Хук для анимации слайда
export const useSlide = (direction = 'up', distance = 20) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);

  const slideIn = () => {
    setIsOpen(true);
    setIsAnimating(true);
  };

  const slideOut = () => {
    setIsAnimating(false);
    setTimeout(() => setIsOpen(false), 300);
  };

  const getTransform = () => {
    if (!isOpen) return 'translateY(100%)';
    if (!isAnimating) return 'translateY(0)';
    
    switch (direction) {
      case 'up': return 'translateY(0)';
      case 'down': return 'translateY(0)';
      case 'left': return 'translateX(0)';
      case 'right': return 'translateX(0)';
      default: return 'translateY(0)';
    }
  };

  return {
    isOpen,
    slideIn,
    slideOut,
    style: {
      transform: getTransform(),
      transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
    }
  };
};

// Хук для анимации вращения
export const useRotate = (initialRotation = 0) => {
  const [rotation, setRotation] = useState(initialRotation);

  const rotate = (degrees) => setRotation(degrees);
  const reset = () => setRotation(initialRotation);

  return {
    rotation,
    rotate,
    reset,
    style: {
      transform: `rotate(${rotation}deg)`,
      transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
    }
  };
};

// Хук для анимации пульсации
export const usePulse = (duration = 1000) => {
  const [isPulsing, setIsPulsing] = useState(false);

  const startPulse = () => setIsPulsing(true);
  const stopPulse = () => setIsPulsing(false);

  return {
    isPulsing,
    startPulse,
    stopPulse,
    style: {
      animation: isPulsing ? `pulse ${duration}ms infinite` : 'none'
    }
  };
};

// Хук для анимации bounce
export const useBounce = () => {
  const [isBouncing, setIsBouncing] = useState(false);

  const bounce = () => {
    setIsBouncing(true);
    setTimeout(() => setIsBouncing(false), 600);
  };

  return {
    isBouncing,
    bounce,
    style: {
      animation: isBouncing ? 'bounce 0.6s ease-in-out' : 'none'
    }
  };
};

// Хук для анимации shake
export const useShake = () => {
  const [isShaking, setIsShaking] = useState(false);

  const shake = () => {
    setIsShaking(true);
    setTimeout(() => setIsShaking(false), 500);
  };

  return {
    isShaking,
    shake,
    style: {
      animation: isShaking ? 'shake 0.5s ease-in-out' : 'none'
    }
  };
};

// Хук для анимации прогресса
export const useProgress = (targetValue = 100, duration = 1000) => {
  const [progress, setProgress] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);

  const startProgress = () => {
    setIsAnimating(true);
    setProgress(0);
    
    const startTime = Date.now();
    const animate = () => {
      const elapsed = Date.now() - startTime;
      const newProgress = Math.min((elapsed / duration) * targetValue, targetValue);
      
      setProgress(newProgress);
      
      if (newProgress < targetValue) {
        requestAnimationFrame(animate);
      } else {
        setIsAnimating(false);
      }
    };
    
    requestAnimationFrame(animate);
  };

  return {
    progress,
    isAnimating,
    startProgress,
    style: {
      width: `${progress}%`,
      transition: 'width 0.1s ease-out'
    }
  };
};

// Хук для анимации stagger (поочередное появление)
export const useStagger = (items, delay = 100) => {
  const [visibleItems, setVisibleItems] = useState([]);

  useEffect(() => {
    const timers = items.map((_, index) => 
      setTimeout(() => {
        setVisibleItems(prev => [...prev, index]);
      }, index * delay)
    );

    return () => timers.forEach(clearTimeout);
  }, [items, delay]);

  return visibleItems;
};
