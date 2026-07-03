import { Card } from '../ui/macos';
import {
  AppError, AppLoading, Button,
} from '../ui/macos';
import { useTheme } from '../../contexts/ThemeContext';
import PropTypes from 'prop-types';

/**
 * Базовый компонент для разделов админ панели
 * Устраняет дублирование в render функциях админ-разделов
 */
const AdminSection = ({ 
  title, 
  description, 
  children, 
  actions = null,
  loading = false,
  error = null,
  className = '',
  ...props 
}) => {
  const { isDark } = useTheme();

  if (loading) {
    return (
      <div className="space-y-6">
        <Card className="p-6">
          <AppLoading
            title={title ? `Загрузка: ${title}` : 'Загрузка раздела'}
            description={description || 'Получаем данные раздела.'}
            size="sm"
          />
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <Card className="p-6">
          <AppError
            title="Ошибка загрузки данных"
            description={error.message || 'Произошла неизвестная ошибка'}
            action={
              <Button type="button" variant="outline" size="small" onClick={() => window.location.reload()}>
                Обновить страницу
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  return (
    <div className={`space-y-6 ${className}`} {...props}>
      <Card className="p-6">
        {/* Заголовок секции */}
        <div className="flex justify-between items-start mb-6">
          <div>
            <h2 className="text-2xl font-bold mb-2" style={{ 
              color: isDark ? '#f8fafc' : '#1e293b' 
            }}>
              {title}
            </h2>
            {description && (
              <p className="text-gray-600" style={{ 
                color: isDark ? '#94a3b8' : '#64748b' 
              }}>
                {description}
              </p>
            )}
          </div>
          
          {/* Действия в заголовке */}
          {actions && (
            <div className="flex gap-2">
              {actions}
            </div>
          )}
        </div>

        {/* Содержимое секции */}
        {children}
      </Card>
    </div>
  );
};


AdminSection.propTypes = {
  ...(AdminSection.propTypes || {}),
  actions: PropTypes.any,
  children: PropTypes.any,
  className: PropTypes.any,
  description: PropTypes.any,
  error: PropTypes.any,
  loading: PropTypes.any,
  title: PropTypes.any,
};

export default AdminSection;


