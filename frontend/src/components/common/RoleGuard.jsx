// Компонент для ролевых ограничений доступа
import PropTypes from 'prop-types';
import { useTheme } from '../../contexts/ThemeContext';
import { hasRouteAccess as hasRouteAccessByRole } from '../../constants/routes';

/**
 * Компонент для проверки ролевого доступа
 */
export function RoleGuard({
  children,
  allowedRoles = [],
  requiredPermissions = [],
  fallback = null,
  profile = null,
  route = null
}) {
  const theme = useTheme();void
  theme;

  // Получаем профиль из контекста или пропсов
  const userProfile = profile || (typeof window !== 'undefined' ?
  JSON.parse(localStorage.getItem('auth_profile') || 'null') : null);

  if (!userProfile) {
    return fallback || <AccessDenied message="Необходима авторизация" theme={theme} />;
  }

  // Проверяем доступ по маршруту
  if (route && !hasRouteAccessByRole(userProfile, route)) {
    return fallback || <AccessDenied message="Недостаточно прав для доступа к этому разделу" theme={theme} />;
  }

  // Проверяем роли
  if (allowedRoles.length > 0) {
    const userRoles = getUserRoles(userProfile);
    const hasRole = allowedRoles.some((role) =>
    userRoles.includes(role.toLowerCase())
    );

    if (!hasRole) {
      return fallback || <AccessDenied message="Недостаточно прав для выполнения этого действия" theme={theme} />;
    }
  }

  // Проверяем разрешения
  if (requiredPermissions.length > 0) {
    const userPermissions = getUserPermissions(userProfile);
    const hasPermission = requiredPermissions.every((permission) =>
    userPermissions.includes(permission)
    );

    if (!hasPermission) {
      return fallback || <AccessDenied message="Недостаточно разрешений для выполнения этого действия" theme={theme} />;
    }
  }

  return children;
}

/**
 * HOC для ролевых ограничений
 */
export function withRoleGuard(WrappedComponent, guardProps = {}) {
  return function WithRoleGuardComponent(props) {
    return (
      <RoleGuard {...guardProps}>
        <WrappedComponent {...props} />
      </RoleGuard>);

  };
}

/**
 * Хук для проверки ролевого доступа
 */
export function useRoleAccess(profile = null) {
  const userProfile = profile || (typeof window !== 'undefined' ?
  JSON.parse(localStorage.getItem('auth_profile') || 'null') : null);

  const hasRole = (roles) => {
    if (!userProfile || !Array.isArray(roles)) return false;
    const userRoles = getUserRoles(userProfile);
    return roles.some((role) => userRoles.includes(role.toLowerCase()));
  };

  const hasPermission = (permissions) => {
    if (!userProfile || !Array.isArray(permissions)) return false;
    const userPermissions = getUserPermissions(userProfile);
    return permissions.every((permission) => userPermissions.includes(permission));
  };

  const hasRouteAccess = (route) => {
    if (!userProfile || !route) return false;
    return hasRouteAccessByRole(userProfile, route);
  };

  const isAdmin = () => {
    return hasRole(['admin', 'Admin']);
  };

  const isDoctor = () => {
    return hasRole(['doctor', 'Doctor', 'cardio', 'derma', 'dentist']);
  };

  const isRegistrar = () => {
    return hasRole(['registrar', 'Registrar', 'receptionist', 'Receptionist']);
  };

  const isLab = () => {
    return hasRole(['lab', 'Lab']);
  };

  const isCashier = () => {
    return hasRole(['cashier', 'Cashier']);
  };

  return {
    profile: userProfile,
    hasRole,
    hasPermission,
    hasRouteAccess,
    isAdmin,
    isDoctor,
    isRegistrar,
    isLab,
    isCashier
  };
}

/**
 * Компонент для условного рендеринга
 */
export function ConditionalRender({
  condition,
  children,
  fallback = null
}) {
  return condition ? children : fallback;
}

/**
 * Компонент для ролевого условного рендеринга
 */
export function RoleConditionalRender({
  roles = [],
  permissions = [],
  children,
  fallback = null,
  profile = null
}) {
  const { hasRole, hasPermission } = useRoleAccess(profile);

  const hasAccess = (roles.length === 0 || hasRole(roles)) && (
  permissions.length === 0 || hasPermission(permissions));

  return hasAccess ? children : fallback;
}

/**
 * Компонент для отображения ошибки доступа
 */
function AccessDenied({ message, theme }) {
  const { getColor, getSpacing, getFontSize } = theme;

  const containerStyle = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '200px',
    padding: getSpacing('lg'),
    textAlign: 'center'
  };

  const iconStyle = {
    fontSize: getFontSize('xxl'),
    marginBottom: getSpacing('md'),
    color: getColor('error', 'main')
  };

  const titleStyle = {
    fontSize: getFontSize('lg'),
    fontWeight: '600',
    color: getColor('text', 'primary'),
    marginBottom: getSpacing('sm')
  };

  const messageStyle = {
    fontSize: getFontSize('md'),
    color: getColor('text', 'secondary'),
    lineHeight: 1.5
  };

  return (
    <div style={containerStyle}>
      <div style={iconStyle}>🚫</div>
      <div style={titleStyle}>Доступ запрещен</div>
      <div style={messageStyle}>{message}</div>
    </div>);

}

/**
 * Утилиты для работы с ролями
 */
function getUserRoles(profile) {
  const roles = [];

  if (profile.role) roles.push(String(profile.role).toLowerCase());
  if (profile.role_name) roles.push(String(profile.role_name).toLowerCase());
  if (Array.isArray(profile.roles)) {
    profile.roles.forEach((r) => roles.push(String(r).toLowerCase()));
  }
  if (profile.is_superuser || profile.is_admin || profile.admin) {
    roles.push('admin');
  }

  return [...new Set(roles)]; // Убираем дубликаты
}

function getUserPermissions(profile) {
  const permissions = [];

  if (Array.isArray(profile.permissions)) {
    permissions.push(...profile.permissions);
  }

  // Добавляем базовые разрешения на основе ролей
  const roles = getUserRoles(profile);

  if (roles.includes('admin')) {
    permissions.push('*'); // Админ имеет все разрешения
  }

  if (roles.includes('doctor')) {
    permissions.push('view_patients', 'edit_patients', 'view_appointments', 'edit_appointments');
  }

  if (roles.includes('registrar') || roles.includes('receptionist')) {
    permissions.push('view_patients', 'edit_patients', 'view_appointments', 'edit_appointments', 'manage_queue');
  }

  if (roles.includes('lab')) {
    permissions.push('view_patients', 'view_appointments', 'manage_lab_results');
  }

  if (roles.includes('cashier')) {
    permissions.push('view_patients', 'view_appointments', 'manage_payments');
  }

  return [...new Set(permissions)]; // Убираем дубликаты
}

/**
 * Компонент для отображения информации о пользователе
 */
export function UserInfo({ profile = null, showRoles = true, showPermissions = false }) {
  const { profile: userProfile } = useRoleAccess(profile);
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  if (!userProfile) return null;

  const containerStyle = {
    padding: getSpacing('md'),
    backgroundColor: getColor('background', 'secondary'),
    borderRadius: '8px',
    border: `1px solid ${getColor('border', 'light')}`
  };

  const titleStyle = {
    fontSize: getFontSize('md'),
    fontWeight: '600',
    color: getColor('text', 'primary'),
    marginBottom: getSpacing('sm')
  };

  const infoStyle = {
    fontSize: getFontSize('sm'),
    color: getColor('text', 'secondary'),
    marginBottom: getSpacing('xs')
  };

  const roles = getUserRoles(userProfile);
  const permissions = getUserPermissions(userProfile);

  return (
    <div style={containerStyle}>
      <div style={titleStyle}>Информация о пользователе</div>
      <div style={infoStyle}>Имя: {userProfile.username || 'Не указано'}</div>
      <div style={infoStyle}>Email: {userProfile.email || 'Не указано'}</div>

      {showRoles &&
      <div style={infoStyle}>
          Роли: {roles.join(', ')}
        </div>
      }

      {showPermissions &&
      <div style={infoStyle}>
          Разрешения: {permissions.join(', ')}
        </div>
      }
    </div>);

}

const profileShape = PropTypes.shape({
  username: PropTypes.string,
  email: PropTypes.string,
  role: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  role_name: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  roles: PropTypes.arrayOf(PropTypes.oneOfType([PropTypes.string, PropTypes.number])),
  permissions: PropTypes.arrayOf(PropTypes.string),
  is_superuser: PropTypes.bool,
  is_admin: PropTypes.bool,
  admin: PropTypes.bool
});

const themeShape = PropTypes.shape({
  getColor: PropTypes.func,
  getSpacing: PropTypes.func,
  getFontSize: PropTypes.func
});

RoleGuard.propTypes = {
  children: PropTypes.node,
  allowedRoles: PropTypes.arrayOf(PropTypes.string),
  requiredPermissions: PropTypes.arrayOf(PropTypes.string),
  fallback: PropTypes.node,
  profile: profileShape,
  route: PropTypes.string
};

ConditionalRender.propTypes = {
  condition: PropTypes.bool,
  children: PropTypes.node,
  fallback: PropTypes.node
};

RoleConditionalRender.propTypes = {
  roles: PropTypes.arrayOf(PropTypes.string),
  permissions: PropTypes.arrayOf(PropTypes.string),
  children: PropTypes.node,
  fallback: PropTypes.node,
  profile: profileShape
};

AccessDenied.propTypes = {
  message: PropTypes.string,
  theme: themeShape
};

UserInfo.propTypes = {
  profile: profileShape,
  showRoles: PropTypes.bool,
  showPermissions: PropTypes.bool
};
