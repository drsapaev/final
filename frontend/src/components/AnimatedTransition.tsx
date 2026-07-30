import { useState, useEffect, ReactNode, CSSProperties } from 'react';


interface AnimatedTransitionProps {
  children: ReactNode;
  type?: 'fade' | 'slide' | 'scale' | 'zoom' | 'rotate';
  duration?: number;
  delay?: number;
  direction?: 'up' | 'down' | 'left' | 'right';
  className?: string;
  style?: CSSProperties;
}

const AnimatedTransition = ({
  children,
  type = 'fade',
  duration = 300,
  delay = 0,
  direction = 'up',
  className = '',
  style = {}
}: AnimatedTransitionProps) => {
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

      case 'slide':{
          const slideTransform = {
            up: isAnimating ? 'translateY(0)' : 'translateY(100%)',
            down: isAnimating ? 'translateY(0)' : 'translateY(-100%)',
            left: isAnimating ? 'translateX(0)' : 'translateX(100%)',
            right: isAnimating ? 'translateX(0)' : 'translateX(-100%)'
          };
          return {
            ...baseStyle,
            opacity: isAnimating ? 1 : 0,
            transform: slideTransform[direction as keyof typeof slideTransform] || slideTransform.up
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
      style={getAnimationStyle()}>
      
      {children}
    </div>);

};

// Компонент для анимированного списка
interface AnimatedListProps<T> {
  items?: T[];
  renderItem: (item: T, index: number) => ReactNode;
  animationType?: 'fade' | 'slide' | 'scale' | 'zoom' | 'rotate';
  staggerDelay?: number;
  className?: string;
  style?: CSSProperties;
}

export const AnimatedList = <T,>({
  items = [],
  renderItem,
  animationType = 'fade',
  staggerDelay = 100,
  className = '',
  style = {}
}: AnimatedListProps<T>) => {
  const [, setVisibleItems] = useState<number[]>([]);

  useEffect(() => {
    const timers = items.map((_, index) =>
    setTimeout(() => {
      setVisibleItems((prev) => [...prev, index]);
    }, index * staggerDelay)
    );

    return () => timers.forEach(clearTimeout);
  }, [items, staggerDelay]);

  return (
    <div className={`animated-list ${className}`} style={style}>
      {items.map((item, index) =>
      <AnimatedTransition
        key={index}
        type={animationType}
        delay={index * staggerDelay}>
        
          {renderItem(item, index)}
        </AnimatedTransition>
      )}
    </div>);

};

// Компонент для анимированной кнопки
interface AnimatedButtonProps {
  children: ReactNode;
  onClick?: React.MouseEventHandler<HTMLButtonElement>;
  variant?: 'primary' | 'secondary' | 'success' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  animationType?: 'fade' | 'slide' | 'scale' | 'zoom' | 'rotate';
  className?: string;
  style?: CSSProperties;
  [key: string]: unknown;
}

export const AnimatedButton = ({
  children,
  onClick,
  variant = 'primary',
  size = 'md',
  animationType = 'scale',
  className = '',
  style = {},
  ...props
}: AnimatedButtonProps) => {
  void animationType;
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
      borderRadius: 'var(--mac-radius-lg)',
      fontWeight: 'var(--mac-font-weight-semibold)',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 'var(--mac-spacing-2)',
      ...style
    };

    // Размеры
    const sizes = {
      sm: { padding: 'var(--mac-spacing-2) var(--mac-spacing-4)', fontSize: 'var(--mac-font-size-base)' },
      md: { padding: 'var(--mac-spacing-3) var(--mac-spacing-6)', fontSize: 'var(--mac-font-size-lg)' },
      lg: { padding: '16px 32px', fontSize: 'var(--mac-font-size-xl)' }
    };

    // Варианты
    const variants = {
      primary: {
        background: 'linear-gradient(135deg, var(--mac-accent-blue) 0%, var(--mac-accent-blue-hover) 100%)',
        color: 'white',
        boxShadow: '0 4px 14px 0 rgba(59, 130, 246, 0.3)'
      },
      secondary: {
        background: 'linear-gradient(135deg, #6b7280 0%, #4b5563 100%)',
        color: 'white',
        boxShadow: '0 4px 14px 0 rgba(107, 114, 128, 0.3)'
      },
      success: {
        background: 'linear-gradient(135deg, var(--mac-success) 0%, var(--mac-success) 100%)',
        color: 'white',
        boxShadow: '0 4px 14px 0 rgba(34, 197, 94, 0.3)'
      },
      danger: {
        background: 'linear-gradient(135deg, var(--mac-error) 0%, var(--mac-error) 100%)',
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
      ...sizes[size as keyof typeof sizes],
      ...variants[variant as keyof typeof variants],
      transform,
      boxShadow: isHovered ?
      variants[variant as keyof typeof variants].boxShadow.replace('0.3', '0.4') :
      variants[variant as keyof typeof variants].boxShadow
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
      {...props}>
      
      {children}
    </button>);

};

// Компонент для анимированной карточки
interface AnimatedCardProps {
  children: ReactNode;
  hover?: boolean;
  className?: string;
  style?: CSSProperties;
  [key: string]: unknown;
}

export const AnimatedCard = ({
  children,
  hover = true,
  className = '',
  style = {},
  ...props
}: AnimatedCardProps) => {
  const [isHovered, setIsHovered] = useState(false);

  const getCardStyle = () => {
    const baseStyle = {
      background: 'rgba(255, 255, 255, 0.8)',
      border: '1px solid rgba(255, 255, 255, 0.2)',
      borderRadius: 'var(--mac-radius-xl)',
      padding: 'var(--mac-spacing-6)',
      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      boxShadow: 'var(--mac-shadow-lg)',
      ...style
    };

    if (hover && isHovered) {
      return {
        ...baseStyle,
        transform: 'translateY(-4px) scale(1.02)',
        boxShadow: 'var(--mac-shadow-xl)'
      };
    }

    return baseStyle;
  };

  return (
    <div
      className={`animated-card ${className}`}
      style={getCardStyle()}
      onPointerEnter={() => setIsHovered(true)}
      onPointerLeave={() => setIsHovered(false)}
      {...props}>
      
      {children}
    </div>);

};





export default AnimatedTransition;
