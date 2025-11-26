import React, { useState, useEffect } from 'react';
import { useFadeIn, useSlide, useScale } from './ui/native';

const AnimatedTransition = ({
  children,
  type = 'fade',
  duration = 300,
  delay = 0,
  direction = 'up',
  className = '',
  style = {}
}) => {
  const [isVisible, setIsVisible] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(true);
      setIsAnimating(true);
    }, delay);

    return () => clearTimeout(timer);
  }, [delay]);

  const getAnimationStyle = () => {
    const baseStyle = {
      transition: `all ${duration}ms cubic-bezier(0.4, 0, 0.2, 1)`,
      ...style
    };

    switch (type) {
      case 'fade':
        return {
          ...baseStyle,
          opacity: isAnimating ? 1 : 0,
          transform: isAnimating ? 'translateY(0)' : 'translateY(20px)'
        };
      
      case 'slide': {
        const slideTransform = {
          up: isAnimating ? 'translateY(0)' : 'translateY(100%)',
          down: isAnimating ? 'translateY(0)' : 'translateY(-100%)',
          left: isAnimating ? 'translateX(0)' : 'translateX(100%)',
          right: isAnimating ? 'translateX(0)' : 'translateX(-100%)'
        };
        return {
          ...baseStyle,
          opacity: isAnimating ? 1 : 0,
          transform: slideTransform[direction] || slideTransform.up
        };
      }
      
      case 'scale':
        return {
          ...baseStyle,
          opacity: isAnimating ? 1 : 0,
          transform: isAnimating ? 'scale(1)' : 'scale(0.8)'
        };
      
      case 'zoom':
        return {
          ...baseStyle,
          opacity: isAnimating ? 1 : 0,
          transform: isAnimating ? 'scale(1)' : 'scale(0)'
        };
      
      case 'rotate':
        return {
          ...baseStyle,
          opacity: isAnimating ? 1 : 0,
          transform: isAnimating ? 'rotate(0deg)' : 'rotate(-180deg)'
        };
      
      default:
        return baseStyle;
    }
  };

  if (!isVisible) return null;

  return (
    <div
      className={`animated-transition ${className}`}
      style={getAnimationStyle()}
    >
      {children}
    </div>
  );
};

// Компонент для анимированного списка
export const AnimatedList = ({
  items = [],
  renderItem,
  animationType = 'fade',
  staggerDelay = 100,
  className = '',
  style = {}
}) => {
  const [visibleItems, setVisibleItems] = useState([]);

  useEffect(() => {
    const timers = items.map((_, index) => 
      setTimeout(() => {
        setVisibleItems(prev => [...prev, index]);
      }, index * staggerDelay)
    );

    return () => timers.forEach(clearTimeout);
  }, [items, staggerDelay]);

  return (
    <div className={`animated-list ${className}`} style={style}>
      {items.map((item, index) => (
        <AnimatedTransition
          key={index}
          type={animationType}
          delay={index * staggerDelay}
        >
          {renderItem(item, index)}
        </AnimatedTransition>
      ))}
    </div>
  );
};

// Компонент для анимированной кнопки
export const AnimatedButton = ({
  children,
  onClick,
  variant = 'primary',
  size = 'md',
  animationType = 'scale',
  className = '',
  style = {},
  ...props
}) => {
  const [isPressed, setIsPressed] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseDown = () => setIsPressed(true);
  const handleMouseUp = () => setIsPressed(false);
  const handleMouseEnter = () => setIsHovered(true);
  const handleMouseLeave = () => setIsHovered(false);

  const getButtonStyle = () => {
    const baseStyle = {
      transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
      cursor: 'pointer',
      border: 'none',
      borderRadius: '12px',
      fontWeight: '600',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '8px',
      ...style
    };

    // Размеры
    const sizes = {
      sm: { padding: '8px 16px', fontSize: '14px' },
      md: { padding: '12px 24px', fontSize: '16px' },
      lg: { padding: '16px 32px', fontSize: '18px' }
    };

    // Варианты
    const variants = {
      primary: {
        background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
        color: 'white',
        boxShadow: '0 4px 14px 0 rgba(59, 130, 246, 0.3)'
      },
      secondary: {
        background: 'linear-gradient(135deg, #6b7280 0%, #4b5563 100%)',
        color: 'white',
        boxShadow: '0 4px 14px 0 rgba(107, 114, 128, 0.3)'
      },
      success: {
        background: 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)',
        color: 'white',
        boxShadow: '0 4px 14px 0 rgba(34, 197, 94, 0.3)'
      },
      danger: {
        background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
        color: 'white',
        boxShadow: '0 4px 14px 0 rgba(239, 68, 68, 0.3)'
      }
    };

    // Анимации
    let transform = 'scale(1)';
    if (isPressed) {
      transform = 'scale(0.95)';
    } else if (isHovered) {
      transform = 'scale(1.05)';
    }

    return {
      ...baseStyle,
      ...sizes[size],
      ...variants[variant],
      transform,
      boxShadow: isHovered 
        ? variants[variant].boxShadow.replace('0.3', '0.4')
        : variants[variant].boxShadow
    };
  };

  return (
    <button
      className={`animated-button ${className}`}
      style={getButtonStyle()}
      onClick={onClick}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      {...props}
    >
      {children}
    </button>
  );
};

// Компонент для анимированной карточки
export const AnimatedCard = ({
  children,
  hover = true,
  className = '',
  style = {},
  ...props
}) => {
  const [isHovered, setIsHovered] = useState(false);

  const getCardStyle = () => {
    const baseStyle = {
      background: 'rgba(255, 255, 255, 0.8)',
      border: '1px solid rgba(255, 255, 255, 0.2)',
      borderRadius: '20px',
      padding: '24px',
      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
      ...style
    };

    if (hover && isHovered) {
      return {
        ...baseStyle,
        transform: 'translateY(-4px) scale(1.02)',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)'
      };
    }

    return baseStyle;
  };

  return (
    <div
      className={`animated-card ${className}`}
      style={getCardStyle()}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      {...props}
    >
      {children}
    </div>
  );
};

export default AnimatedTransition;

