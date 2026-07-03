import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Card, Button } from '../ui/macos';
import logger from '../../utils/logger';
import PropTypes from 'prop-types';

let errorBoundaryInstance = 0;

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
    errorBoundaryInstance += 1;
    this.titleId = `admin-error-boundary-title-${errorBoundaryInstance}`;
    this.descriptionId = `admin-error-boundary-description-${errorBoundaryInstance}`;
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({
      error: error,
      errorInfo: errorInfo
    });

    // Логируем ошибку в консоль для разработки
    logger.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <Card
          className="p-6"
          role="alert"
          aria-live="assertive"
          aria-labelledby={this.titleId}
          aria-describedby={this.descriptionId}>
          <div className="text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center"
            aria-hidden="true"
            style={{ background: 'var(--danger-color)', opacity: 0.1 }}>
              <AlertTriangle className="w-8 h-8" focusable="false" style={{ color: 'var(--danger-color)' }} />
            </div>
            
            <h2 id={this.titleId} className="text-xl font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
              Что-то пошло не так
            </h2>
            
            <p id={this.descriptionId} className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
              Произошла ошибка при загрузке этого раздела. Попробуйте обновить страницу.
            </p>
            
            <div className="flex gap-3 justify-center">
              <Button type="button" onClick={this.handleRetry} variant="primary">
                <RefreshCw className="w-4 h-4 mr-2" aria-hidden="true" focusable="false" />
                Попробовать снова
              </Button>
              
              <Button
                type="button"
                onClick={() => window.location.reload()}
                variant="outline">
                
                Обновить страницу
              </Button>
            </div>
            
            {process.env.NODE_ENV === 'development' && this.state.error &&
            <details className="mt-4 text-left">
                <summary className="cursor-pointer text-sm font-medium mb-2"
              style={{ color: 'var(--text-secondary)' }}>
                  Детали ошибки (только для разработки)
                </summary>
                <pre className="text-xs p-3 rounded bg-gray-100 overflow-auto"
              style={{
                background: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)'
              }}>
                  {this.state.error && this.state.error.toString()}
                  {this.state.errorInfo.componentStack}
                </pre>
              </details>
            }
          </div>
        </Card>);

    }

    return this.props.children;
  }
}


ErrorBoundary.propTypes = {
  ...(ErrorBoundary.propTypes || {}),
  children: PropTypes.any,
};

export default ErrorBoundary;
