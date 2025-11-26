// Компоненты для отображения состояния загрузки
import React from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import AnimatedLoader from '../AnimatedLoader.jsx';

/**
 * Основной компонент загрузки
 */
export function Loading({ 
  size = 'medium', 
  variant = 'spinner', 
  text = 'Загрузка...', 
  overlay = false,
  fullScreen = false,
  color = 'primary'
}) {
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  const getSize = (size) => {
    const sizes = {
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
          <div style={dotsStyle}>
            {[0, 1, 2].map(i => (
              <div
                key={i}
                style={{
                  ...dotStyle,
                  animationDelay: `${i * 0.16}s`
                }}
              />
            ))}
          </div>
        );
      
      case 'pulse':
        return <div style={pulseStyle} />;
      
      case 'spinner':
      default:
        return <div style={spinnerStyle} />;
    }
  };

  return (
    <div style={containerStyle}>
      {renderLoader()}
      {text && <div style={textStyle}>{text}</div>}
    </div>
  );
}

/**
 * Компонент для загрузки кнопки
 */
export function ButtonLoading({ loading, children, ...props }) {
  const theme = useTheme();
  const { getColor, getSpacing } = theme;

  const buttonStyle = {
    position: 'relative',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: getSpacing('sm'),
    ...props.style
  };

  const spinnerStyle = {
    width: '16px',
    height: '16px',
    border: '2px solid transparent',
    borderTop: '2px solid currentColor',
    borderRadius: '50%',
    animation: 'spin 1s linear infinite'
  };

  return (
    <button {...props} style={buttonStyle} disabled={loading || props.disabled}>
      {loading && <div style={spinnerStyle} />}
      {children}
    </button>
  );
}

/**
 * Компонент для загрузки таблицы (использует AnimatedLoader)
 */
export function TableLoading({ columns = 3, rows = 5 }) {
  // Используем улучшенный AnimatedLoader
  return <AnimatedLoader.TableSkeleton rows={rows} columns={columns} />;
}

/**
 * Компонент для загрузки таблицы (старая версия)
 */
export function TableLoadingOld({ columns = 3, rows = 5 }) {
  const theme = useTheme();
  const { getColor, getSpacing } = theme;

  const tableStyle = {
    width: '100%',
    borderCollapse: 'collapse'
  };

  const cellStyle = {
    padding: getSpacing('md'),
    borderBottom: `1px solid ${getColor('border', 'light')}`
  };

  const skeletonStyle = {
    backgroundColor: getColor('background', 'tertiary'),
    borderRadius: '4px',
    height: '20px',
    animation: 'skeleton 1.5s ease-in-out infinite'
  };

  return (
    <table style={tableStyle}>
      <thead>
        <tr>
          {Array.from({ length: columns }).map((_, i) => (
            <th key={i} style={cellStyle}>
              <div style={skeletonStyle} />
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <tr key={rowIndex}>
            {Array.from({ length: columns }).map((_, colIndex) => (
              <td key={colIndex} style={cellStyle}>
                <div style={skeletonStyle} />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * Компонент для загрузки карточек (использует AnimatedLoader)
 */
export function CardLoading({ count = 3 }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '20px' }}>
      {Array.from({ length: count }).map((_, i) => (
        <AnimatedLoader.CardSkeleton key={i} />
      ))}
    </div>
  );
}

/**
 * Компонент для загрузки карточек (старая версия)
 */
export function CardLoadingOld({ count = 3 }) {
  const theme = useTheme();
  const { getColor, getSpacing } = theme;

  const containerStyle = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
    gap: getSpacing('lg')
  };

  const cardStyle = {
    padding: getSpacing('lg'),
    backgroundColor: getColor('background', 'secondary'),
    borderRadius: '8px',
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)'
  };

  const skeletonStyle = {
    backgroundColor: getColor('background', 'tertiary'),
    borderRadius: '4px',
    height: '20px',
    marginBottom: getSpacing('sm'),
    animation: 'skeleton 1.5s ease-in-out infinite'
  };

  return (
    <div style={containerStyle}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} style={cardStyle}>
          <div style={{ ...skeletonStyle, height: '24px', marginBottom: getSpacing('md') }} />
          <div style={{ ...skeletonStyle, width: '80%' }} />
          <div style={{ ...skeletonStyle, width: '60%' }} />
          <div style={{ ...skeletonStyle, width: '40%' }} />
        </div>
      ))}
    </div>
  );
}

/**
 * Компонент для загрузки списка
 */
export function ListLoading({ count = 5 }) {
  const theme = useTheme();
  const { getColor, getSpacing } = theme;

  const containerStyle = {
    display: 'flex',
    flexDirection: 'column',
    gap: getSpacing('md')
  };

  const itemStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('md'),
    padding: getSpacing('md'),
    backgroundColor: getColor('background', 'secondary'),
    borderRadius: '8px'
  };

  const avatarStyle = {
    width: '40px',
    height: '40px',
    backgroundColor: getColor('background', 'tertiary'),
    borderRadius: '50%',
    animation: 'skeleton 1.5s ease-in-out infinite'
  };

  const contentStyle = {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: getSpacing('xs')
  };

  const skeletonStyle = {
    backgroundColor: getColor('background', 'tertiary'),
    borderRadius: '4px',
    height: '16px',
    animation: 'skeleton 1.5s ease-in-out infinite'
  };

  return (
    <div style={containerStyle}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} style={itemStyle}>
          <div style={avatarStyle} />
          <div style={contentStyle}>
            <div style={{ ...skeletonStyle, width: '60%' }} />
            <div style={{ ...skeletonStyle, width: '40%' }} />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Хук для управления состоянием загрузки
 */
export function useLoading(initialState = false) {
  const [loading, setLoading] = React.useState(initialState);

  const startLoading = React.useCallback(() => {
    setLoading(true);
  }, []);

  const stopLoading = React.useCallback(() => {
    setLoading(false);
  }, []);

  const withLoading = React.useCallback(async (asyncFunction) => {
    try {
      startLoading();
      const result = await asyncFunction();
      return result;
    } finally {
      stopLoading();
    }
  }, [startLoading, stopLoading]);

  return {
    loading,
    startLoading,
    stopLoading,
    withLoading
  };
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

