import { getEffectiveRouteByPath, getProfileRoles, getRoleHomeRoute, hasRouteAccess as hasRegistryRouteAccess, normalizeRole, routeToRoles as routeRolesFromRegistry } from '../routing/routeSelectors';

export function roleToRoute(role: string): string {
  return getRoleHomeRoute(role);
}

export function routeToRoles(route: string): string[] {
  return routeRolesFromRegistry(route);
}

export function hasRouteAccess(profile: Record<string, unknown>, route: string): boolean {
  return hasRegistryRouteAccess(profile, route, { internalDemoEnabled: false });
}

export function getRouteForProfile(profile: Record<string, unknown> | null): string {
  return getRoleHomeRoute(profile);
}

export function getRouteMetadata(route: string) {
  return getEffectiveRouteByPath(route);
}

export function getUserRoles(profile: Record<string, unknown>): string[] {
  return getProfileRoles(profile);
}

export const ROLE_OPTIONS = [
  { key: 'admin', label: 'Администратор', username: 'admin@example.com', route: roleToRoute('admin') },
  { key: 'registrar', label: 'Регистратура', username: 'registrar@example.com', route: roleToRoute('registrar') },
  { key: 'lab', label: 'Лаборатория', username: 'lab@example.com', route: roleToRoute('lab') },
  { key: 'doctor', label: 'Врач', username: 'doctor@example.com', route: roleToRoute('doctor') },
  { key: 'cashier', label: 'Касса', username: 'cashier@example.com', route: roleToRoute('cashier') },
  { key: 'cardio', label: 'Кардиолог', username: 'cardio@example.com', route: roleToRoute('cardio') },
  { key: 'derma', label: 'Дерматолог', username: 'derma@example.com', route: roleToRoute('derma') },
  { key: 'dentist', label: 'Стоматолог', username: 'dentist@example.com', route: roleToRoute('dentist') },
  { key: 'patient', label: 'Пациент', username: 'patient@example.com', route: roleToRoute('patient') },
];

export { normalizeRole };
