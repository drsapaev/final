// Компонент для защищенных маршрутов с ролевыми ограничениями
import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { RequireAuth, RequireRoles, RequirePermissions } from '../auth/RequireAuth';
import { useRoleAccess } from '../common/RoleGuard';

/**
 * Компонент для создания защищенных маршрутов
 */
export function ProtectedRoute({ 
  path, 
  element, 
  roles = [], 
  permissions = [],
  requireAuth = true,
  fallback = null,
  ...props 
}) {
  if (!requireAuth) {
    return <Route path={path} element={element} {...props} />;
  }

  if (roles.length > 0) {
    return (
      <Route 
        path={path} 
        element={
          <RequireRoles roles={roles} fallback={fallback}>
            {element}
          </RequireRoles>
        } 
        {...props} 
      />
    );
  }

  if (permissions.length > 0) {
    return (
      <Route 
        path={path} 
        element={
          <RequirePermissions permissions={permissions} fallback={fallback}>
            {element}
          </RequirePermissions>
        } 
        {...props} 
      />
    );
  }

  return (
    <Route 
      path={path} 
      element={
        <RequireAuth fallback={fallback}>
          {element}
        </RequireAuth>
      } 
      {...props} 
    />
  );
}

/**
 * Компонент для создания группы защищенных маршрутов
 */
export function ProtectedRouteGroup({ 
  children, 
  roles = [], 
  permissions = [],
  requireAuth = true,
  fallback = null 
}) {
  if (!requireAuth) {
    return <>{children}</>;
  }

  if (roles.length > 0) {
    return (
      <RequireRoles roles={roles} fallback={fallback}>
        {children}
      </RequireRoles>
    );
  }

  if (permissions.length > 0) {
    return (
      <RequirePermissions permissions={permissions} fallback={fallback}>
        {children}
      </RequirePermissions>
    );
  }

  return (
    <RequireAuth fallback={fallback}>
      {children}
    </RequireAuth>
  );
}

/**
 * Компонент для условного рендеринга маршрутов
 */
export function ConditionalRoute({ 
  condition, 
  children, 
  fallback = null 
}) {
  return condition ? children : fallback;
}

/**
 * Компонент для ролевого условного рендеринга маршрутов
 */
export function RoleBasedRoute({ 
  roles = [], 
  permissions = [],
  children, 
  fallback = null,
  requireAll = false
}) {
  const { profile, hasRole, hasPermission } = useRoleAccess();

  if (!profile) {
    return fallback;
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

  return hasAccess ? children : fallback;
}

/**
 * Компонент для создания маршрутов на основе ролей
 */
export function RoleBasedRoutes({ 
  routes = [], 
  fallback = null 
}) {
  return (
    <Routes>
      {routes.map((route, index) => (
        <RoleBasedRoute
          key={index}
          roles={route.roles}
          permissions={route.permissions}
          fallback={fallback}
        >
          <Route 
            path={route.path} 
            element={route.element} 
            {...route.props} 
          />
        </RoleBasedRoute>
      ))}
    </Routes>
  );
}

/**
 * Компонент для создания навигационного меню с ролевыми ограничениями
 */
export function RoleBasedNavigation({ 
  items = [], 
  fallback = null 
}) {
  const { profile, hasRole, hasPermission } = useRoleAccess();

  if (!profile) {
    return fallback;
  }

  const visibleItems = items.filter(item => {
    if (item.roles && item.roles.length > 0) {
      return hasRole(item.roles);
    }
    if (item.permissions && item.permissions.length > 0) {
      return hasPermission(item.permissions);
    }
    return true;
  });

  return <>{visibleItems}</>;
}

/**
 * Компонент для создания бокового меню с ролевыми ограничениями
 */
export function RoleBasedSidebar({ 
  sections = [], 
  fallback = null 
}) {
  const { profile, hasRole, hasPermission } = useRoleAccess();

  if (!profile) {
    return fallback;
  }

  const visibleSections = sections.filter(section => {
    if (section.roles && section.roles.length > 0) {
      return hasRole(section.roles);
    }
    if (section.permissions && section.permissions.length > 0) {
      return hasPermission(section.permissions);
    }
    return true;
  });

  return <>{visibleSections}</>;
}

/**
 * Компонент для создания кнопок действий с ролевыми ограничениями
 */
export function RoleBasedActions({ 
  actions = [], 
  fallback = null 
}) {
  const { profile, hasRole, hasPermission } = useRoleAccess();

  if (!profile) {
    return fallback;
  }

  const visibleActions = actions.filter(action => {
    if (action.roles && action.roles.length > 0) {
      return hasRole(action.roles);
    }
    if (action.permissions && action.permissions.length > 0) {
      return hasPermission(action.permissions);
    }
    return true;
  });

  return <>{visibleActions}</>;
}

/**
 * Хук для создания ролевых маршрутов
 */
export function useRoleBasedRoutes() {
  const { profile, hasRole, hasPermission } = useRoleAccess();

  const createRoute = (route) => {
    if (!profile) return null;

    if (route.roles && route.roles.length > 0) {
      return hasRole(route.roles) ? route : null;
    }

    if (route.permissions && route.permissions.length > 0) {
      return hasPermission(route.permissions) ? route : null;
    }

    return route;
  };

  const createRoutes = (routes) => {
    return routes
      .map(createRoute)
      .filter(Boolean);
  };

  const createNavigationItems = (items) => {
    return items.filter(item => {
      if (item.roles && item.roles.length > 0) {
        return hasRole(item.roles);
      }
      if (item.permissions && item.permissions.length > 0) {
        return hasPermission(item.permissions);
      }
      return true;
    });
  };

  return {
    createRoute,
    createRoutes,
    createNavigationItems,
    profile,
    hasRole,
    hasPermission
  };
}

