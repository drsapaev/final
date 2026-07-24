import type { CSSProperties, ReactNode, ComponentType } from "react";

// Компонент для ролевых ограничений маршрутов
import { Navigate, useLocation } from 'react-router-dom';
import { useTheme } from '../../contexts/ThemeContext';
import { useRoleAccess } from '../common/RoleGuard';
import { Loading } from '../common/Loading';
import { useTranslation } from '../../i18n/useTranslation';

interface RequireAuthProps {
  children: ReactNode;
  roles?: string[];
  permissions?: string[];
  fallback?: ReactNode;
  redirectTo?: string;
}

/**
 * Компонент для проверки аутентификации и ролевого доступа
 */
export function RequireAuth({
  children,
  roles = [],
  permissions = [],
  fallback = null,
  redirectTo = '/login'
}: RequireAuthProps) {
  const location = useLocation();
  const { profile, hasRole, hasPermission } = useRoleAccess();

  if (!profile) {
    return <Navigate to={redirectTo} state={{ from: location }} replace />;
  }

  if (roles.length > 0 && !hasRole(roles)) {
    return <>{fallback}</> || <Navigate to="/unauthorized" replace />;
  }

  if (permissions.length > 0 && !hasPermission(permissions)) {
    return <>{fallback}</> || <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
}

interface RequireAuthOnlyProps {
  children: ReactNode;
  redirectTo?: string;
}

/**
 * Компонент для проверки только аутентификации
 */
export function RequireAuthOnly({ children, redirectTo = '/login' }: RequireAuthOnlyProps) {
  const location = useLocation();
  const { profile } = useRoleAccess();

  if (!profile) {
    return <Navigate to={redirectTo} state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

interface RequireRolesProps {
  children: ReactNode;
  roles?: string[];
  fallback?: ReactNode;
}

/**
 * Компонент для проверки ролей без аутентификации
 */
export function RequireRoles({ children, roles = [], fallback = null }: RequireRolesProps) {
  const { profile, hasRole } = useRoleAccess();

  if (!profile) {
    return <Loading text="Загрузка..." />;
  }

  if (roles.length > 0 && !hasRole(roles)) {
    return <>{fallback}</> || <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
}

interface RequirePermissionsProps {
  children: ReactNode;
  permissions?: string[];
  fallback?: ReactNode;
}

/**
 * Компонент для проверки разрешений
 */
export function RequirePermissions({ children, permissions = [], fallback = null }: RequirePermissionsProps) {
  const { profile, hasPermission } = useRoleAccess();

  if (!profile) {
    return <Loading text="Загрузка..." />;
  }

  if (permissions.length > 0 && !hasPermission(permissions)) {
    return <>{fallback}</> || <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
}

interface RoleBasedRenderProps {
  children: ReactNode;
  roles?: string[];
  permissions?: string[];
  fallback?: ReactNode;
  requireAll?: boolean;
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
}: RoleBasedRenderProps) {
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

  return hasAccess ? <>{children}</> : (<>{fallback}</>);
}

/**
 * HOC для ролевых ограничений
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function withRoleAuth(WrappedComponent: ComponentType<any>, authProps: Record<string, unknown> = {}) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return function WithRoleAuthComponent(props: any) {
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
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function withRoleRender(WrappedComponent: ComponentType<any>, renderProps: Record<string, unknown> = {}) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return function WithRoleRenderComponent(props: any) {
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

  const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    padding: getSpacing('lg'),
    textAlign: 'center'
  };

  const iconStyle: CSSProperties = {
    fontSize: getFontSize('xxl'),
    marginBottom: getSpacing('lg'),
    color: getColor('error', 'main')
  };

  const titleStyle: CSSProperties = {
    fontSize: getFontSize('xl'),
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: getColor('text', 'primary'),
    marginBottom: getSpacing('md')
  };

  const messageStyle: CSSProperties = {
    fontSize: getFontSize('md'),
    color: getColor('text', 'secondary'),
    marginBottom: getSpacing('lg'),
    maxWidth: '500px',
    lineHeight: 1.6
  };

  const buttonStyle: CSSProperties = {
    padding: `${getSpacing('sm')} ${getSpacing('lg')}`,
    backgroundColor: getColor('primary', 'main'),
    color: getColor('primary', 'contrast'),
    border: 'none',
    borderRadius: 'var(--mac-radius-md)',
    fontSize: getFontSize('md'),
    fontWeight: 'var(--mac-font-weight-medium)',
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
