import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Card, Button } from '../ui/native';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({
      error: error,
      errorInfo: errorInfo
    });
    
    // Логируем ошибку в консоль для разработки
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <Card className="p-6">
          <div className="text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center" 
                 style={{ background: 'var(--danger-color)', opacity: 0.1 }}>
              <AlertTriangle className="w-8 h-8" style={{ color: 'var(--danger-color)' }} />
            </div>
            
            <h2 className="text-xl font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
              Что-то пошло не так
            </h2>
            
            <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
              Произошла ошибка при загрузке этого раздела. Попробуйте обновить страницу.
            </p>
            
            <div className="flex gap-3 justify-center">
              <Button onClick={this.handleRetry} variant="primary">
                <RefreshCw className="w-4 h-4 mr-2" />
                Попробовать снова
              </Button>
              
              <Button 
                onClick={() => window.location.reload()} 
                variant="outline"
              >
                Обновить страницу
              </Button>
            </div>
            
            {process.env.NODE_ENV === 'development' && this.state.error && (
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
            )}
          </div>
        </Card>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;

