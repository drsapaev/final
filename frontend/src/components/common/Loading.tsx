
// Компоненты для отображения состояния загрузки
import React, { type CSSProperties } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import AnimatedLoader from '../AnimatedLoader';
import { useTranslation } from '../../i18n/useTranslation';

/**
 * Основной компонент загрузки
 */
interface LoadingProps {
  size?: string;
  variant?: string;
  text?: string;
  overlay?: boolean;
  fullScreen?: boolean;
  color?: string;
}

export function Loading({
  size = 'medium',
  variant = 'spinner',
  text = 'Загрузка...',
  overlay = false,
  fullScreen = false,
  color = 'primary'
}: LoadingProps = {}) {
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  const getSize = (size: string): string => {
    const sizes: Record<string, string> = {
      small: '20px',
      medium: '40px',
      large: '60px',
      xlarge: '80px'
    };
    return sizes[size] || sizes.medium;
  };

  const spinnerStyle = {
    width: getSize(size),
    height: getSize(size),
    border: `3px solid ${getColor('background', 'tertiary')}`,
    borderTop: `3px solid ${getColor(color, 'main')}`,
    borderRadius: '50%',
    animation: 'spin 1s linear infinite',
    margin: '0 auto'
  };

  const dotsStyle = {
    display: 'flex',
    gap: getSpacing('xs'),
    justifyContent: 'center',
    alignItems: 'center'
  };

  const dotStyle = {
    width: '8px',
    height: '8px',
    backgroundColor: getColor(color, 'main'),
    borderRadius: '50%',
    animation: 'bounce 1.4s ease-in-out infinite both'
  };

  const pulseStyle = {
    width: getSize(size),
    height: getSize(size),
    backgroundColor: getColor(color, 'main'),
    borderRadius: '50%',
    animation: 'pulse 1.5s ease-in-out infinite'
  };

  const textStyle = {
    marginTop: getSpacing('md'),
    fontSize: getFontSize('md'),
    color: getColor('text', 'secondary'),
    textAlign: 'center'
  };

  const containerStyle = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: getSpacing('lg'),
    ...(overlay && {
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(255, 255, 255, 0.8)',
      zIndex: 1000
    }),
    ...(fullScreen && {
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: getColor('background', 'primary'),
      zIndex: 9999
    })
  };

  const renderLoader = () => {
    switch (variant) {
      case 'dots':
        return (
          <div style={dotsStyle as CSSProperties}>
            {[0, 1, 2].map((i) =>
            <div
              key={i}
              style={{
                ...dotStyle,
                animationDelay: `${i * 0.16}s`
              } as CSSProperties} />

            )}
          </div>);


      case 'pulse':
        return <div style={pulseStyle as CSSProperties} />;

      case 'spinner':
      default:
        return <div style={spinnerStyle as CSSProperties} />;
    }
  };

  return (
    <div style={containerStyle as CSSProperties}>
      {renderLoader()}
      {text && <div style={textStyle as CSSProperties}>{text}</div>}
    </div>);

}

/**
 * Компонент для загрузки таблицы (использует AnimatedLoader)
 */
export function TableLoading({ columns = 3, rows = 5 }) {
  // Используем улучшенный AnimatedLoader
  return <AnimatedLoader.TableSkeleton rows={rows} columns={columns} />;
}












// CSS анимации
const style = document.createElement('style');
style.textContent = `
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  @keyframes bounce {
    0%, 80%, 100% { transform: scale(0); }
    40% { transform: scale(1); }
  }
  
  @keyframes pulse {
    0% { transform: scale(0.95); opacity: 1; }
    70% { transform: scale(1); opacity: 0.7; }
    100% { transform: scale(0.95); opacity: 1; }
  }
  
  @keyframes skeleton {
    0% { opacity: 1; }
    50% { opacity: 0.5; }
    100% { opacity: 1; }
  }
`;
document.head.appendChild(style);
