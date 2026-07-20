import { useEffect, useState, type ReactNode } from 'react';
import PropTypes from 'prop-types';
import { Navigate, useLocation } from 'react-router-dom';
import auth from '../stores/auth.js';
import type { AuthState } from '../stores/auth';
import logger from '../utils/logger';
import {
  getEffectiveRouteByPath,
  getLegacyRedirectTarget,
  getProfileRoles,
  isInternalDemoEnabled,
  normalizeRole,
} from './routeSelectors.js';
import { useTranslation } from '../i18n/useTranslation';

// Reuse the route selector's structural type so we don't duplicate the
// field list. routeGuards only inspects id, group, auth, roles.
type GuardedRoute = Parameters<typeof getEffectiveRouteByPath>[0] extends infer R
  ? R extends null
    ? null
    : { id: string; group: string; auth: string; roles: string[]; [key: string]: unknown }
  : never;

interface RouteProfile {
  role?: string;
  role_name?: string;
  roles?: string[];
  is_superuser?: boolean;
  is_admin?: boolean;
  admin?: boolean;
  username?: string;
  email?: string;
  specialty?: string;
  [key: string]: unknown;
}

interface RouteAccessBoundaryProps {
  route: GuardedRoute | null;
  children?: ReactNode;
}

interface SystemRoutePageProps {
  title: string;
  description: string;
  code: string;
}

function isSameAuthState(prev: AuthState, next: AuthState): boolean {
  return prev.token === next.token &&
    JSON.stringify(prev.profile || null) === JSON.stringify(next.profile || null);
}

function canAccessRoute(route: GuardedRoute | null, profile: RouteProfile | null | undefined): boolean {
  if (!route) {
    return false;
  }
  if (route.group === 'internal-demo' && !isInternalDemoEnabled()) {
    return false;
  }
  if (route.auth === 'public') {
    return true;
  }
  if (!profile) {
    return false;
  }
  if (route.auth === 'authenticated') {
    return true;
  }

  const currentRoles = getProfileRoles(profile);
  return route.roles.some((role) => currentRoles.includes(normalizeRole(role)));
}

export function resolveSetupRedirect(pathname: string, initialized: boolean): string | null {
  const route = getEffectiveRouteByPath(pathname) as GuardedRoute | null;
  if (!route) {
    return initialized ? null : '/setup';
  }

  if (!initialized) {
    if (route.group === 'clinical' || route.group === 'admin') {
      return '/setup';
    }
    return null;
  }

  if (initialized && route.group === 'onboarding') {
    return '/login';
  }

  return null;
}

export function RouteAccessBoundary({ route, children }: RouteAccessBoundaryProps) {
  const { t } = useTranslation();
  void t;
  const [state, setState] = useState<AuthState>(() => auth.getState());
  const [isChecking, setIsChecking] = useState<boolean>(() => Boolean(auth.getToken()) && route?.auth !== 'public');
  const location = useLocation();

  useEffect(() => {
    let isMounted = true;
    const unsubscribe = auth.subscribe((nextState: AuthState) => {
      if (!isMounted) return;
      setState((prevState) => (isSameAuthState(prevState, nextState) ? prevState : nextState));
    });

    const validateSession = async (): Promise<void> => {
      if (!route || route.auth === 'public') {
        if (isMounted) setIsChecking(false);
        return;
      }
      const token = auth.getToken();
      if (!token) {
        if (isMounted) setIsChecking(false);
        return;
      }

      try {
        logger.info('[routing] validating protected route session', {
          routeId: route.id,
          path: location.pathname,
        });
        const nextState = await auth.validateSession();
        if (isMounted) {
          setState((prevState) => (isSameAuthState(prevState, nextState) ? prevState : nextState));
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'unknown error';
        logger.warn('[routing] protected route validation failed', {
          routeId: route.id,
          path: location.pathname,
          error: message,
        });
      } finally {
        if (isMounted) setIsChecking(false);
      }
    };

    void validateSession();

    return () => {
      isMounted = false;
      unsubscribe();
    };
  }, [location.pathname, route]);

  if (!route) {
    return <Navigate to="/not-found" replace />;
  }

  if (route.group === 'internal-demo' && !isInternalDemoEnabled()) {
    return <Navigate to="/not-found" replace />;
  }

  if (isChecking) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        Загрузка...
      </div>
    );
  }

  if (route.auth !== 'public' && !state.token) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (!canAccessRoute(route, state.profile as RouteProfile | null)) {
    return <Navigate to={route.auth === 'authenticated' ? '/unauthorized' : '/forbidden'} replace />;
  }

  return children;
}

RouteAccessBoundary.propTypes = {
  route: PropTypes.shape({
    id: PropTypes.string.isRequired,
    group: PropTypes.string,
    auth: PropTypes.string,
    roles: PropTypes.arrayOf(PropTypes.string),
  }),
  children: PropTypes.node,
};

export function LegacyRouteRedirect() {
  const location = useLocation();
  const redirect = getLegacyRedirectTarget(location.pathname);

  if (!redirect) {
    return <Navigate to="/not-found" replace />;
  }

  const target = `${redirect.targetPath}${location.search || ''}${location.hash || ''}`;
  return <Navigate to={target} replace />;
}

function SystemRoutePage({ title, description, code }: SystemRoutePageProps) {
  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '32px',
      background: 'var(--mac-bg-page, #f5f7fb)',
    }}>
      <div style={{
        maxWidth: '560px',
        width: '100%',
        borderRadius: 'var(--mac-radius-xl)',
        border: '1px solid var(--mac-border, #d8dde8)',
        background: 'var(--mac-bg-primary, #ffffff)',
        boxShadow: '0 16px 40px rgba(15, 23, 42, 0.08)',
        padding: '32px',
        textAlign: 'center',
      }}>
        <div style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-bold)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--mac-text-secondary, #5f6b7a)' }}>
          {code}
        </div>
        <h1 style={{ margin: '12px 0 8px', fontSize: 'var(--mac-font-size-3xl)', lineHeight: 1.1, color: 'var(--mac-text-primary, #111827)' }}>
          {title}
        </h1>
        <p style={{ margin: 0, fontSize: 'var(--mac-font-size-lg)', lineHeight: 1.6, color: 'var(--mac-text-secondary, #4b5563)' }}>
          {description}
        </p>
      </div>
    </div>
  );
}

SystemRoutePage.propTypes = {
  title: PropTypes.string.isRequired,
  description: PropTypes.string.isRequired,
  code: PropTypes.string.isRequired,
};

export function UnauthorizedPage() {
  const { t } = useTranslation();
  const tr = t as (key: string) => string;
  return (
    <SystemRoutePage
      code="401"
      title={tr('misc.rg_trebuetsya_vhod')}
      description={tr('misc.rg_voydite_v_sistemu_chtoby_otk')}
    />
  );
}

export function ForbiddenPage() {
  const { t } = useTranslation();
  const tr = t as (key: string) => string;
  return (
    <SystemRoutePage
      code="403"
      title={tr('misc.rg_dostup_zapreschyon')}
      description={tr('misc.rg_u_vashey_uchyotnoy_zapisi_ne')}
    />
  );
}

export function NotFoundPage() {
  const { t } = useTranslation();
  const tr = t as (key: string) => string;
  return (
    <SystemRoutePage
      code="404"
      title={tr('misc.rg_stranitsa_ne_naydena')}
      description={tr('misc.rg_zaproshennyy_marshrut_ne_vho')}
    />
  );
}
