
// Error Boundary для обработки ошибок React
import i18n from '../../i18n';
import React, { type CSSProperties, type ErrorInfo, type ReactNode } from 'react';

import { Button } from '../ui/macos';
import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';
interface ErrorBoundaryProps {
  children: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  theme?: Record<string, unknown> | null;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

/**
 * Error Boundary компонент для перехвата и обработки ошибок React
 */
class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError() {
    // Обновляем состояние для отображения fallback UI
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Логируем ошибку
    logger.error('ErrorBoundary caught an error:', error, errorInfo);

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
          theme={this.props.theme} />);


    }

    return this.props.children;
  }
}


// audit/strict: removed self-referencing propTypes spread

interface ErrorFallbackProps {
  error: Error | null;
  errorInfo: ErrorInfo | null;
  onRetry: () => void;
  theme?: Record<string, unknown> | null;
}

/**
 * Fallback UI компонент
 */
function ErrorFallback({ error, errorInfo, onRetry, theme }: ErrorFallbackProps) {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // Проверяем, что theme существует и имеет необходимые методы
  type ThemeFn = (...args: unknown[]) => string;
  const themeObj = theme as Record<string, unknown> | null | undefined;
  const getColor = ((themeObj?.getColor as ThemeFn | undefined) ?? ((color: string) => color)) as ThemeFn;
  const getSpacing = ((themeObj?.getSpacing as ThemeFn | undefined) ?? ((size: string) => size)) as ThemeFn;
  const getFontSize = ((themeObj?.getFontSize as ThemeFn | undefined) ?? ((size: string) => size)) as ThemeFn;

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
    borderRadius: 'var(--mac-radius-lg)',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.1)',
    textAlign: 'center'
  };

  const titleStyle = {
    fontSize: getFontSize('xl'),
    fontWeight: 'var(--mac-font-weight-bold)',
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
    borderRadius: 'var(--mac-radius-md)',
    fontSize: getFontSize('md'),
    fontWeight: 'var(--mac-font-weight-medium)',
    cursor: 'pointer',
    transition: 'all 0.2s ease'
  };

  const detailsStyle = {
    marginTop: getSpacing('lg'),
    padding: getSpacing('md'),
    backgroundColor: getColor('background', 'tertiary'),
    borderRadius: 'var(--mac-radius-md)',
    fontSize: getFontSize('sm'),
    color: getColor('text', 'tertiary'),
    textAlign: 'left',
    maxHeight: '200px',
    overflow: 'auto'
  };

  return (
    <div style={containerStyle as CSSProperties}>
      <div style={cardStyle as CSSProperties}>
        <h1 style={titleStyle as CSSProperties}>Что-то пошло не так</h1>
        <p style={messageStyle as CSSProperties}>
          Произошла неожиданная ошибка. Мы уже работаем над её исправлением.
        </p>
        
        <Button
          variant="primary"
          onClick={onRetry}>
          
          Попробовать снова
        </Button>

        {process.env.NODE_ENV === 'development' && error &&
        <details style={detailsStyle as CSSProperties}>
            <summary style={{ cursor: 'pointer', marginBottom: getSpacing('sm') }}>
              Детали ошибки (только для разработки)
            </summary>
            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {error.toString()}
              {errorInfo && errorInfo.componentStack}
            </pre>
          </details>
        }
      </div>
    </div>);

}


// audit/strict: removed self-referencing propTypes spread

/**
 * HOC для обертывания компонентов в Error Boundary
 */
export function withErrorBoundary<P extends Record<string, unknown>>(
  WrappedComponent: React.ComponentType<P>,
  errorBoundaryProps: Partial<ErrorBoundaryProps> = {}
) {
  return function WithErrorBoundaryComponent(props: P) {
    return (
      <ErrorBoundary {...errorBoundaryProps}>
        <WrappedComponent {...props} />
      </ErrorBoundary>);

  };
}

/**
 * Хук для управления состоянием error boundary в функциональных компонентах.
 *
 * Renamed from `useErrorHandler` to `useErrorBoundaryState` per ADR-0016,
 * to avoid collision with `utils/errorHandler.ts:useErrorHandler` (which
 * returns a function, not an error-state triple).
 */
export function useErrorBoundaryState() {
  const [error, setError] = React.useState<Error | null>(null);

  const resetError = React.useCallback(() => {
    setError(null);
  }, []);

  const handleError = React.useCallback((error: Error) => {
    logger.error('Error caught by useErrorBoundaryState:', error);
    setError(error);
  }, []);

  React.useEffect(() => {
    if (error) {
      // Можно добавить отправку ошибки в систему мониторинга
      logger.error('Unhandled error:', error);
    }
  }, [error]);

  return { error, handleError, resetError };
}

export default ErrorBoundary;