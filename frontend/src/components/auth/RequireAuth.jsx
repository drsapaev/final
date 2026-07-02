// Компонент для ролевых ограничений маршрутов
import PropTypes from 'prop-types';
import { Navigate, useLocation } from 'react-router-dom';
import { useTheme } from '../../contexts/ThemeContext';
import { useRoleAccess } from '../common/RoleGuard';
import { Loading } from '../common/Loading';

/**
 * Компонент для проверки аутентификации и ролевого доступа
 */
export function RequireAuth({ 
  children, 
  roles = [], 
  permissions = [],
  fallback = null,
  redirectTo = '/login'
}) {
  const location = useLocation();
  const { profile, hasRole, hasPermission } = useRoleAccess();

  // Если нет профиля, перенаправляем на логин
  if (!profile) {
    return <Navigate to={redirectTo} state={{ from: location }} replace />;
  }

  // Проверяем роли
  if (roles.length > 0 && !hasRole(roles)) {
    return fallback || <Navigate to="/unauthorized" replace />;
  }

  // Проверяем разрешения
  if (permissions.length > 0 && !hasPermission(permissions)) {
    return fallback || <Navigate to="/unauthorized" replace />;
  }

  return children;
}

/**
 * Компонент для проверки только аутентификации
 */
export function RequireAuthOnly({ children, redirectTo = '/login' }) {
  const location = useLocation();
  const { profile } = useRoleAccess();

  if (!profile) {
    return <Navigate to={redirectTo} state={{ from: location }} replace />;
  }

  return children;
}

/**
 * Компонент для проверки ролей без аутентификации
 */
export function RequireRoles({ children, roles = [], fallback = null }) {
  const { profile, hasRole } = useRoleAccess();

  if (!profile) {
    return <Loading text="Загрузка..." />;
  }

  if (roles.length > 0 && !hasRole(roles)) {
    return fallback || <Navigate to="/unauthorized" replace />;
  }

  return children;
}

/**
 * Компонент для проверки разрешений
 */
export function RequirePermissions({ children, permissions = [], fallback = null }) {
  const { profile, hasPermission } = useRoleAccess();

  if (!profile) {
    return <Loading text="Загрузка..." />;
  }

  if (permissions.length > 0 && !hasPermission(permissions)) {
    return fallback || <Navigate to="/unauthorized" replace />;
  }

  return children;
}

/**
 * Компонент для условного рендеринга на основе ролей
 */
export function RoleBasedRender({ 
  children, 
  roles = [], 
  permissions = [],
  fallback = null,
  requireAll = false
}) {
  const { profile, hasRole, hasPermission } = useRoleAccess();

  if (!profile) {
    return <Loading text="Загрузка..." />;
  }

  let hasAccess = true;

  if (roles.length > 0) {
    hasAccess = requireAll ? 
      roles.every(role => hasRole([role])) : 
      hasRole(roles);
  }

  if (permissions.length > 0) {
    const hasPerms = requireAll ? 
      permissions.every(permission => hasPermission([permission])) : 
      hasPermission(permissions);
    
    hasAccess = hasAccess && hasPerms;
  }

  return hasAccess ? children : (fallback || null);
}

/**
 * HOC для ролевых ограничений
 */
export function withRoleAuth(WrappedComponent, authProps = {}) {
  return function WithRoleAuthComponent(props) {
    return (
      <RequireAuth {...authProps}>
        <WrappedComponent {...props} />
      </RequireAuth>
    );
  };
}

/**
 * HOC для ролевого рендеринга
 */
export function withRoleRender(WrappedComponent, renderProps = {}) {
  return function WithRoleRenderComponent(props) {
    return (
      <RoleBasedRender {...renderProps}>
        <WrappedComponent {...props} />
      </RoleBasedRender>
    );
  };
}

/**
 * Компонент для отображения страницы неавторизованного доступа
 */
export function UnauthorizedPage() {
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  const containerStyle = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    padding: getSpacing('lg'),
    textAlign: 'center'
  };

  const iconStyle = {
    fontSize: getFontSize('xxl'),
    marginBottom: getSpacing('lg'),
    color: getColor('error', 'main')
  };

  const titleStyle = {
    fontSize: getFontSize('xl'),
    fontWeight: '600',
    color: getColor('text', 'primary'),
    marginBottom: getSpacing('md')
  };

  const messageStyle = {
    fontSize: getFontSize('md'),
    color: getColor('text', 'secondary'),
    marginBottom: getSpacing('lg'),
    maxWidth: '500px',
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
    textDecoration: 'none',
    display: 'inline-block'
  };

  return (
    <div style={containerStyle}>
      <div style={iconStyle}>🚫</div>
      <h1 style={titleStyle}>Доступ запрещен</h1>
      <p style={messageStyle}>
        У вас нет прав для доступа к этой странице. 
        Обратитесь к администратору для получения необходимых разрешений.
      </p>
      <a href="/" style={buttonStyle}>
        Вернуться на главную
      </a>
    </div>
  );
}

RequireAuth.propTypes = {
  children: PropTypes.node,
  roles: PropTypes.arrayOf(PropTypes.string),
  permissions: PropTypes.arrayOf(PropTypes.string),
  fallback: PropTypes.node,
  redirectTo: PropTypes.string
};

RequireAuthOnly.propTypes = {
  children: PropTypes.node,
  redirectTo: PropTypes.string
};

RequireRoles.propTypes = {
  children: PropTypes.node,
  roles: PropTypes.arrayOf(PropTypes.string),
  fallback: PropTypes.node
};

RequirePermissions.propTypes = {
  children: PropTypes.node,
  permissions: PropTypes.arrayOf(PropTypes.string),
  fallback: PropTypes.node
};

RoleBasedRender.propTypes = {
  children: PropTypes.node,
  roles: PropTypes.arrayOf(PropTypes.string),
  permissions: PropTypes.arrayOf(PropTypes.string),
  fallback: PropTypes.node,
  requireAll: PropTypes.bool
};
