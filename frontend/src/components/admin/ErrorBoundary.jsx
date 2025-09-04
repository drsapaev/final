import React from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';

const ErrorBoundary = ({ children, fallback = null }) => {
  const [hasError, setHasError] = React.useState(false);
  const [error, setError] = React.useState(null);
  const { theme, getColor, getSpacing, getFontSize } = useTheme();

  React.useEffect(() => {
    const handleError = (error, errorInfo) => {
      console.error('AdminPanel Error:', error, errorInfo);
      setHasError(true);
      setError(error);
    };

    // Глобальный обработчик ошибок
    window.addEventListener('error', handleError);
    window.addEventListener('unhandledrejection', handleError);

    return () => {
      window.removeEventListener('error', handleError);
      window.removeEventListener('unhandledrejection', handleError);
    };
  }, []);

  const handleRetry = () => {
    setHasError(false);
    setError(null);
    window.location.reload();
  };

  const handleGoHome = () => {
    window.location.href = '/admin';
  };

  if (hasError) {
    if (fallback) {
      return fallback;
    }

    const errorStyle = {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '400px',
      padding: getSpacing('xl'),
      textAlign: 'center',
      background: theme === 'light' 
        ? 'rgba(255, 255, 255, 0.9)' 
        : 'rgba(15, 23, 42, 0.9)',
      backdropFilter: 'blur(20px)',
      border: `1px solid ${theme === 'light' ? 'rgba(255, 255, 255, 0.3)' : 'rgba(255, 255, 255, 0.1)'}`,
      borderRadius: '20px',
      boxShadow: theme === 'light' 
        ? '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
        : '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.1)'
    };

    const iconStyle = {
      width: '64px',
      height: '64px',
      color: getColor('danger', 500),
      marginBottom: getSpacing('lg')
    };

    const titleStyle = {
      fontSize: getFontSize('xl'),
      fontWeight: '700',
      color: 'var(--text-primary)',
      marginBottom: getSpacing('md')
    };

    const messageStyle = {
      fontSize: getFontSize('md'),
      color: 'var(--text-secondary)',
      marginBottom: getSpacing('lg'),
      maxWidth: '500px',
      lineHeight: 1.6
    };

    const buttonStyle = {
      display: 'flex',
      gap: getSpacing('md'),
      flexWrap: 'wrap',
      justifyContent: 'center'
    };

    const retryButtonStyle = {
      display: 'flex',
      alignItems: 'center',
      gap: getSpacing('sm'),
      padding: `${getSpacing('sm')} ${getSpacing('lg')}`,
      background: getColor('primary', 500),
      color: 'white',
      border: 'none',
      borderRadius: '12px',
      fontSize: getFontSize('sm'),
      fontWeight: '600',
      cursor: 'pointer',
      transition: 'all 0.2s ease',
      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
    };

    const homeButtonStyle = {
      ...retryButtonStyle,
      background: theme === 'light' ? 'var(--bg-secondary)' : 'var(--bg-tertiary)',
      color: 'var(--text-primary)',
      border: `1px solid var(--border-color)`
    };

    return (
      <div style={errorStyle}>
        <AlertTriangle style={iconStyle} />
        <h2 style={titleStyle}>Что-то пошло не так</h2>
        <p style={messageStyle}>
          Произошла ошибка в админ-панели. Это может быть временная проблема. 
          Попробуйте обновить страницу или вернуться на главную.
        </p>
        {process.env.NODE_ENV === 'development' && error && (
          <details style={{ 
            marginBottom: getSpacing('lg'),
            padding: getSpacing('md'),
            background: theme === 'light' ? 'var(--bg-secondary)' : 'var(--bg-tertiary)',
            borderRadius: '8px',
            fontSize: getFontSize('xs'),
            color: 'var(--text-tertiary)',
            textAlign: 'left',
            maxWidth: '100%',
            overflow: 'auto'
          }}>
            <summary style={{ cursor: 'pointer', marginBottom: getSpacing('sm') }}>
              Детали ошибки (только в режиме разработки)
            </summary>
            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {error.toString()}
            </pre>
          </details>
        )}
        <div style={buttonStyle}>
          <button onClick={handleRetry} style={retryButtonStyle}>
            <RefreshCw size={16} />
            Обновить страницу
          </button>
          <button onClick={handleGoHome} style={homeButtonStyle}>
            <Home size={16} />
            На главную
          </button>
        </div>
      </div>
    );
  }

  return children;
};

export default ErrorBoundary;
