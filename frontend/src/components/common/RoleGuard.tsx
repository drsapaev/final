import React, { type CSSProperties, type ReactNode, type ComponentType } from 'react';

// Компонент для ролевых ограничений доступа
import { useTheme } from '../../contexts/ThemeContext';
import { getProfileRoles, hasRouteAccess as hasRouteAccessByRole, normalizeRole } from '../../routing/routeSelectors';
import { useTranslation } from '../../i18n/useTranslation';
import i18n from '../../i18n';
import { safeJsonParse } from '../../utils/safeJsonParse';
const t18 = i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string;

interface RoleGuardProps {
  children: ReactNode;
  allowedRoles?: string[];
  requiredPermissions?: string[];
  fallback?: ReactNode;
  profile?: Record<string, unknown> | null;
  route?: string | null;
}

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
}: RoleGuardProps) {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const theme = useTheme();
  theme;

  // Получаем профиль из контекста или пропсов
  const userProfile = profile || (typeof window !== 'undefined' ?
  safeJsonParse(sessionStorage.getItem('auth_profile') || 'null') : null);

  if (!userProfile) {
    return fallback || <AccessDenied message={t18('misc.rg_neobhodima_avtorizatsiya')} theme={theme} />;
  }

  // Проверяем доступ по маршруту
  if (route && !hasRouteAccessByRole(userProfile, route)) {
    return fallback || <AccessDenied message={t18('misc.rg_nedostatochno_prav_dlya_dost')} theme={theme} />;
  }

  // Проверяем роли
  if (allowedRoles.length > 0) {
    const userRoles = getUserRoles(userProfile);
    const hasRole = allowedRoles.some((role) =>
    userRoles.includes(normalizeRole(role))
    );

    if (!hasRole) {
      return fallback || <AccessDenied message={t18('misc.rg_nedostatochno_prav_dlya_vypo')} theme={theme} />;
    }
  }

  // Проверяем разрешения
  if (requiredPermissions.length > 0) {
    const userPermissions = getUserPermissions(userProfile);
    const hasPermission = requiredPermissions.every((permission) =>
    userPermissions.includes(permission)
    );

    if (!hasPermission) {
      return fallback || <AccessDenied message={t18('misc.rg_nedostatochno_razresheniy_dl')} theme={theme} />;
    }
  }

  return children;
}

/**
 * HOC для ролевых ограничений
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function withRoleGuard(WrappedComponent: ComponentType<any>, guardProps: Record<string, unknown> = {}) {
  // TECH-DEBT(role-guard-hoc): props is `any` because this is a generic HOC
  // that wraps any component. The props are passed through opaquely.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return function WithRoleGuardComponent(props: any) {
    return (
      <RoleGuard {...guardProps}>
        <WrappedComponent {...props} />
      </RoleGuard>);

  };
}

/**
 * Хук для проверки ролевого доступа
 */
export function useRoleAccess(profile: Record<string, unknown> | null = null) {
  const userProfile = profile || (typeof window !== 'undefined' ?
  safeJsonParse(sessionStorage.getItem('auth_profile') || 'null') : null);

  const hasRole = (roles: string[]) => {
  if (!userProfile || !Array.isArray(roles)) return false;
    const userRoles = getUserRoles(userProfile);
    return roles.some((role) => userRoles.includes(normalizeRole(role)));
  };

  const hasPermission = (permissions: string[]) => {
    if (!userProfile || !Array.isArray(permissions)) return false;
    const userPermissions = getUserPermissions(userProfile);
    return permissions.every((permission) => userPermissions.includes(permission));
  };

  const hasRouteAccess = (route: string) => {
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
interface ConditionalRenderProps {
  condition: boolean;
  children: ReactNode;
  fallback?: ReactNode;
}

export function ConditionalRender({
  condition,
  children,
  fallback = null
}: ConditionalRenderProps) {
  return condition ? <>{children}</> : <>{fallback}</>;
}

/**
 * Компонент для ролевого условного рендеринга
 */
interface RoleConditionalRenderProps {
  roles?: string[];
  permissions?: string[];
  children: ReactNode;
  fallback?: ReactNode;
  profile?: Record<string, unknown> | null;
}

export function RoleConditionalRender({
  roles = [],
  permissions = [],
  children,
  fallback = null,
  profile = null
}: RoleConditionalRenderProps) {
  const { hasRole, hasPermission } = useRoleAccess(profile);

  const hasAccess = (roles.length === 0 || hasRole(roles)) && (
  permissions.length === 0 || hasPermission(permissions));

  return hasAccess ? children : fallback;
}

/**
 * Компонент для отображения ошибки доступа
 */
function AccessDenied({ message, theme }: { message: string; theme: ReturnType<typeof useTheme> }) {
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
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: getColor('text', 'primary'),
    marginBottom: getSpacing('sm')
  };

  const messageStyle = {
    fontSize: getFontSize('md'),
    color: getColor('text', 'secondary'),
    lineHeight: 1.5
  };

  return (
    <div style={containerStyle as CSSProperties}>
      <div style={iconStyle as CSSProperties}>🚫</div>
      <div style={titleStyle as CSSProperties}>{t18('misc.rg_dostup_zapreschen')}</div>
      <div style={messageStyle as CSSProperties}>{message}</div>
    </div>);

}

/**
 * Утилиты для работы с ролями
 */
function getUserRoles(profile: Record<string, unknown>): string[] {
  return getProfileRoles(profile);
}

function getUserPermissions(profile: Record<string, unknown>): string[] {
  const permissions: string[] = [];

  if (Array.isArray(profile.permissions)) {
    permissions.push(...(profile.permissions as string[]));
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
export function UserInfo({ profile = null, showRoles = true, showPermissions = false }: { profile?: Record<string, unknown> | null; showRoles?: boolean; showPermissions?: boolean } = {}) {
  const { profile: userProfile } = useRoleAccess(profile);
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  if (!userProfile) return null;

  const containerStyle = {
    padding: getSpacing('md'),
    backgroundColor: getColor('background', 'secondary'),
    borderRadius: 'var(--mac-radius-md)',
    border: `1px solid ${getColor('border', 'light')}`
  };

  const titleStyle = {
    fontSize: getFontSize('md'),
    fontWeight: 'var(--mac-font-weight-semibold)',
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
    <div style={containerStyle as CSSProperties}>
      <div style={titleStyle as CSSProperties}>{t18('misc.rg_informatsiya_o_polzovatele')}</div>
      <div style={infoStyle as CSSProperties}>Имя: {userProfile.username || t18('misc.rg_ne_ukazano')}</div>
      <div style={infoStyle as CSSProperties}>Email: {userProfile.email || t18('misc.rg_ne_ukazano')}</div>

      {showRoles &&
      <div style={infoStyle as CSSProperties}>
          Роли: {roles.join(', ')}
        </div>
      }

      {showPermissions &&
      <div style={infoStyle as CSSProperties}>
          Разрешения: {permissions.join(', ')}
        </div>
      }
    </div>);

}





