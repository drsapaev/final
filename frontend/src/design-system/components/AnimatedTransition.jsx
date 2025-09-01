import React, { useState, useEffect } from 'react';
import { ANIMATION_TYPES, ANIMATION_DIRECTIONS } from './types';

const AnimatedTransition = ({
  children,
  type = ANIMATION_TYPES.FADE,
  duration = 300,
  delay = 0,
  direction = ANIMATION_DIRECTIONS.UP,
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
      case ANIMATION_TYPES.FADE:
        return {
          ...baseStyle,
          opacity: isAnimating ? 1 : 0,
          transform: isAnimating ? 'translateY(0)' : 'translateY(20px)'
        };
      
      case ANIMATION_TYPES.SLIDE: {
        const slideTransform = {
          [ANIMATION_DIRECTIONS.UP]: isAnimating ? 'translateY(0)' : 'translateY(100%)',
          [ANIMATION_DIRECTIONS.DOWN]: isAnimating ? 'translateY(0)' : 'translateY(-100%)',
          [ANIMATION_DIRECTIONS.LEFT]: isAnimating ? 'translateX(0)' : 'translateX(100%)',
          [ANIMATION_DIRECTIONS.RIGHT]: isAnimating ? 'translateX(0)' : 'translateX(-100%)'
        };
        return {
          ...baseStyle,
          opacity: isAnimating ? 1 : 0,
          transform: slideTransform[direction] || slideTransform[ANIMATION_DIRECTIONS.UP]
        };
      }
      
      case ANIMATION_TYPES.SCALE:
        return {
          ...baseStyle,
          opacity: isAnimating ? 1 : 0,
          transform: isAnimating ? 'scale(1)' : 'scale(0.8)'
        };
      
      case ANIMATION_TYPES.ZOOM:
        return {
          ...baseStyle,
          opacity: isAnimating ? 1 : 0,
          transform: isAnimating ? 'scale(1)' : 'scale(0)'
        };
      
      case ANIMATION_TYPES.ROTATE:
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
      className={`design-system-animated-transition ${className}`}
      style={getAnimationStyle()}
    >
      {children}
    </div>
  );
};

export default AnimatedTransition;
