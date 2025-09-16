// Error Boundary для обработки ошибок React
import React from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { Button } from '../../design-system/components';

/**
 * Error Boundary компонент для перехвата и обработки ошибок React
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    // Обновляем состояние для отображения fallback UI
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Логируем ошибку
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    
    this.setState({
      error: error,
      errorInfo: errorInfo
    });

    // Отправляем ошибку в систему мониторинга (если есть)
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      // Fallback UI
      return (
        <ErrorFallback 
          error={this.state.error}
          errorInfo={this.state.errorInfo}
          onRetry={this.handleRetry}
          theme={this.props.theme}
        />
      );
    }

    return this.props.children;
  }
}

/**
 * Fallback UI компонент
 */
function ErrorFallback({ error, errorInfo, onRetry, theme }) {
  // Проверяем, что theme существует и имеет необходимые методы
  const getColor = theme?.getColor || ((color) => color);
  const getSpacing = theme?.getSpacing || ((size) => size);
  const getFontSize = theme?.getFontSize || ((size) => size);

  const containerStyle = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    padding: getSpacing('lg'),
    backgroundColor: getColor('background', 'primary'),
    color: getColor('text', 'primary')
  };

  const cardStyle = {
    maxWidth: '600px',
    width: '100%',
    padding: getSpacing('xl'),
    backgroundColor: getColor('background', 'secondary'),
    borderRadius: '12px',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.1)',
    textAlign: 'center'
  };

  const titleStyle = {
    fontSize: getFontSize('xl'),
    fontWeight: 'bold',
    color: getColor('error', 'primary'),
    marginBottom: getSpacing('md')
  };

  const messageStyle = {
    fontSize: getFontSize('md'),
    color: getColor('text', 'secondary'),
    marginBottom: getSpacing('lg'),
    lineHeight: 1.6
  };

  const buttonStyle = {
    padding: `${getSpacing('sm')} ${getSpacing('lg')}`,
    backgroundColor: getColor('primary', 'main'),
    color: getColor('primary', 'contrast'),
    border: 'none',
    borderRadius: '8px',
    fontSize: getFontSize('md'),
    fontWeight: '500',
    cursor: 'pointer',
    transition: 'all 0.2s ease'
  };

  const detailsStyle = {
    marginTop: getSpacing('lg'),
    padding: getSpacing('md'),
    backgroundColor: getColor('background', 'tertiary'),
    borderRadius: '8px',
    fontSize: getFontSize('sm'),
    color: getColor('text', 'tertiary'),
    textAlign: 'left',
    maxHeight: '200px',
    overflow: 'auto'
  };

  return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        <h1 style={titleStyle}>Что-то пошло не так</h1>
        <p style={messageStyle}>
          Произошла неожиданная ошибка. Мы уже работаем над её исправлением.
        </p>
        
        <Button 
          variant="primary"
          onClick={onRetry}
        >
          Попробовать снова
        </Button>

        {process.env.NODE_ENV === 'development' && error && (
          <details style={detailsStyle}>
            <summary style={{ cursor: 'pointer', marginBottom: getSpacing('sm') }}>
              Детали ошибки (только для разработки)
            </summary>
            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {error.toString()}
              {errorInfo && errorInfo.componentStack}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}

/**
 * HOC для обертывания компонентов в Error Boundary
 */
export function withErrorBoundary(WrappedComponent, errorBoundaryProps = {}) {
  return function WithErrorBoundaryComponent(props) {
    return (
      <ErrorBoundary {...errorBoundaryProps}>
        <WrappedComponent {...props} />
      </ErrorBoundary>
    );
  };
}

/**
 * Хук для обработки ошибок в функциональных компонентах
 */
export function useErrorHandler() {
  const [error, setError] = React.useState(null);

  const resetError = React.useCallback(() => {
    setError(null);
  }, []);

  const handleError = React.useCallback((error) => {
    console.error('Error caught by useErrorHandler:', error);
    setError(error);
  }, []);

  React.useEffect(() => {
    if (error) {
      // Можно добавить отправку ошибки в систему мониторинга
      console.error('Unhandled error:', error);
    }
  }, [error]);

  return { error, handleError, resetError };
}

export default ErrorBoundary;
