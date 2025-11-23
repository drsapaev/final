/**
 * Улучшенная система анимаций для медицинских интерфейсов
 * Основана на принципах доступности и медицинских стандартах UX
 */

import React, { useState, useEffect, useRef } from 'react';

// macOS-совместимые анимации
export const animations = {
  // Простые переходы
  fade: {
    enter: { opacity: 0 },
    enterActive: { 
      opacity: 1, 
      transition: 'opacity var(--mac-duration-normal) var(--mac-ease)' 
    },
    exit: { opacity: 1 },
    exitActive: { 
      opacity: 0, 
      transition: 'opacity var(--mac-duration-normal) var(--mac-ease)' 
    }
  },

  slideUp: {
    enter: { opacity: 0, transform: 'translateY(16px)' },
    enterActive: { 
      opacity: 1, 
      transform: 'translateY(0)', 
      transition: 'all var(--mac-duration-normal) var(--mac-ease)' 
    },
    exit: { opacity: 1, transform: 'translateY(0)' },
    exitActive: { 
      opacity: 0, 
      transform: 'translateY(8px)', 
      transition: 'all var(--mac-duration-normal) var(--mac-ease)' 
    }
  },

  slideDown: {
    enter: { opacity: 0, transform: 'translateY(-16px)' },
    enterActive: { 
      opacity: 1, 
      transform: 'translateY(0)', 
      transition: 'all var(--mac-duration-normal) var(--mac-ease)' 
    },
    exit: { opacity: 1, transform: 'translateY(0)' },
    exitActive: { 
      opacity: 0, 
      transform: 'translateY(-8px)', 
      transition: 'all var(--mac-duration-normal) var(--mac-ease)' 
    }
  },

  slideLeft: {
    enter: { opacity: 0, transform: 'translateX(16px)' },
    enterActive: { 
      opacity: 1, 
      transform: 'translateX(0)', 
      transition: 'all var(--mac-duration-normal) var(--mac-ease)' 
    },
    exit: { opacity: 1, transform: 'translateX(0)' },
    exitActive: { 
      opacity: 0, 
      transform: 'translateX(8px)', 
      transition: 'all var(--mac-duration-normal) var(--mac-ease)' 
    }
  },

  slideRight: {
    enter: { opacity: 0, transform: 'translateX(-16px)' },
    enterActive: { 
      opacity: 1, 
      transform: 'translateX(0)', 
      transition: 'all var(--mac-duration-normal) var(--mac-ease)' 
    },
    exit: { opacity: 1, transform: 'translateX(0)' },
    exitActive: { 
      opacity: 0, 
      transform: 'translateX(-8px)', 
      transition: 'all var(--mac-duration-normal) var(--mac-ease)' 
    }
  },

  scale: {
    enter: { opacity: 0, transform: 'scale(0.95)' },
    enterActive: { 
      opacity: 1, 
      transform: 'scale(1)', 
      transition: 'all var(--mac-duration-normal) var(--mac-ease)' 
    },
    exit: { opacity: 1, transform: 'scale(1)' },
    exitActive: { 
      opacity: 0, 
      transform: 'scale(0.95)', 
      transition: 'all var(--mac-duration-normal) var(--mac-ease)' 
    }
  },

  // Специфичные для медицинских интерфейсов
  modal: {
    enter: { opacity: 0, transform: 'scale(0.95) translateY(16px)' },
    enterActive: { 
      opacity: 1, 
      transform: 'scale(1) translateY(0)', 
      transition: 'all var(--mac-duration-normal) var(--mac-ease)' 
    },
    exit: { opacity: 1, transform: 'scale(1) translateY(0)' },
    exitActive: { 
      opacity: 0, 
      transform: 'scale(0.95) translateY(16px)', 
      transition: 'all var(--mac-duration-normal) var(--mac-ease)' 
    }
  },

  dropdown: {
    enter: { opacity: 0, transform: 'translateY(-8px)' },
    enterActive: { 
      opacity: 1, 
      transform: 'translateY(0)', 
      transition: 'all var(--mac-duration-normal) var(--mac-ease)' 
    },
    exit: { opacity: 1, transform: 'translateY(0)' },
    exitActive: { 
      opacity: 0, 
      transform: 'translateY(-8px)', 
      transition: 'all var(--mac-duration-normal) var(--mac-ease)' 
    }
  },

  tableRow: {
    enter: { opacity: 0, transform: 'translateX(100%)' },
    enterActive: { 
      opacity: 1, 
      transform: 'translateX(0)', 
      transition: 'all var(--mac-duration-normal) var(--mac-ease)' 
    },
    exit: { opacity: 1, transform: 'translateX(0)' },
    exitActive: { 
      opacity: 0, 
      transform: 'translateX(100%)', 
      transition: 'all var(--mac-duration-normal) var(--mac-ease)' 
    }
  }
};

// Хук для анимации появления/исчезновения
export const useAnimation = (isVisible, animationType = 'fade', duration = 300) => {
  const [animationState, setAnimationState] = useState('hidden');
  const [shouldRender, setShouldRender] = useState(false);
  const timeoutRef = useRef(null);

  useEffect(() => {
    if (isVisible) {
      setShouldRender(true);
      setAnimationState('entering');

      timeoutRef.current = setTimeout(() => {
        setAnimationState('entered');
      }, 10);
    } else {
      setAnimationState('exiting');

      timeoutRef.current = setTimeout(() => {
        setAnimationState('exited');
        setShouldRender(false);
      }, duration);
    }

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [isVisible, duration]);

  const getAnimationStyles = () => {
    const animation = animations[animationType];
    if (!animation) return {};

    switch (animationState) {
      case 'entering':
        return animation.enter;
      case 'entered':
        return animation.enterActive;
      case 'exiting':
        return animation.exit;
      case 'exited':
        return animation.exitActive;
      default:
        return animation.enter;
    }
  };

  return {
    shouldRender,
    animationStyles: getAnimationStyles(),
    animationState
  };
};

// Хук для анимации списка
export const useListAnimation = (items, animationType = 'tableRow') => {
  const [animatedItems, setAnimatedItems] = useState([]);

  useEffect(() => {
    const newItems = items.map((item, index) => ({
      ...item,
      animationDelay: index * 50 // Задержка между элементами
    }));

    setAnimatedItems(newItems);
  }, [items, animationType]);

  return animatedItems;
};

// Хук для анимации прогресса
export const useProgressAnimation = (targetValue, duration = 1000) => {
  const [currentValue, setCurrentValue] = useState(0);

  useEffect(() => {
    const startTime = Date.now();
    const startValue = currentValue;

    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Используем easing функцию
      const easedProgress = 1 - Math.pow(1 - progress, 3);
      const newValue = startValue + (targetValue - startValue) * easedProgress;

      setCurrentValue(newValue);

      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };

    requestAnimationFrame(animate);
  }, [targetValue, duration]);

  return currentValue;
};

// Компонент анимированного перехода
export const AnimatedTransition = ({
  children,
  isVisible,
  animationType = 'fade',
  duration = 300,
  delay = 0,
  className = '',
  ...props
}) => {
  const { shouldRender, animationClasses } = useAnimation(isVisible, animationType, duration);

  if (!shouldRender) return null;

  return (
    <div
      className={`animated-transition ${animationClasses} ${className}`}
      style={{
        transitionDelay: `${delay}ms`,
        ...props.style
      }}
      {...props}
    >
      {children}
    </div>
  );
};

// Компонент анимированного списка
export const AnimatedList = ({
  items,
  renderItem,
  animationType = 'tableRow',
  className = '',
  ...props
}) => {
  const animatedItems = useListAnimation(items, animationType);

  return (
    <div className={`animated-list ${className}`} {...props}>
      {animatedItems.map((item, index) => (
        <div
          key={item.id || index}
          className={`animated-list-item ${animations[animationType]?.enter}`}
          style={{
            animationDelay: `${item.animationDelay}ms`,
            animation: `slideInUp 0.3s ease-out ${item.animationDelay}ms both`
          }}
        >
          {renderItem(item, index)}
        </div>
      ))}

      <style>
        {`
          @keyframes slideInUp {
            from {
              opacity: 0;
              transform: translateY(20px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }
        `}
      </style>
    </div>
  );
};

// Компонент анимированного прогресса
export const AnimatedProgress = ({
  value,
  max = 100,
  animationDuration = 1000,
  showValue = true,
  className = '',
  ...props
}) => {
  const animatedValue = useProgressAnimation(value, animationDuration);
  const percentage = (animatedValue / max) * 100;

  return (
    <div className={`animated-progress ${className}`} {...props}>
      <div
        className="progress-bar"
        style={{
          width: `${percentage}%`,
          height: '8px',
          backgroundColor: '#3b82f6',
          borderRadius: '4px',
          transition: 'width 0.3s ease'
        }}
      />
      {showValue && (
        <div style={{ marginTop: '4px', fontSize: '12px', color: '#6b7280' }}>
          {Math.round(animatedValue)} / {max}
        </div>
      )}
    </div>
  );
};

// Компонент анимированного счетчика
export const AnimatedCounter = ({
  value,
  duration = 1000,
  format = (v) => v.toLocaleString(),
  className = '',
  ...props
}) => {
  const animatedValue = useProgressAnimation(value, duration);

  return (
    <span className={`animated-counter ${className}`} {...props}>
      {format(Math.round(animatedValue))}
    </span>
  );
};

// Утилита для создания кастомных анимаций
export const createAnimation = (config) => {
  return {
    enter: config.enter || 'opacity-0',
    enterActive: config.enterActive || 'opacity-100 transition-all duration-300',
    exit: config.exit || 'opacity-100',
    exitActive: config.exitActive || 'opacity-0 transition-all duration-300'
  };
};

export default useAnimation;
