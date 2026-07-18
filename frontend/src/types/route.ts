// src/types/route.ts
// Phase 0.5 — Route registry types.
// Plan: JS-to-TS-Migration-Plan v3, section 6 (defined here for early use).
//
// SSOT: frontend/src/routing/routeRegistry.js
// Roles: imported from roles.ts (which mirrors backend/app/core/roles.py).

import type { BackendRole, FrontendRoleKey } from './roles';

// ============================================================================
// Route classification enums (string-literal unions; no runtime enum to keep
// import-cost low and to align with `as const` style used elsewhere).
// ============================================================================

export type RouteGroup = 'public' | 'onboarding' | 'clinical' | 'admin' | 'internal-demo';
export type RouteSurface = 'screen' | 'modal-route' | 'callback' | 'utility';
export type RouteLifecycle = 'stable' | 'compatibility' | 'experimental' | 'internal';
export type RouteShell = 'landing' | 'app-shell' | 'fullscreen' | 'callback' | 'setup';
export type RouteAuth = 'public' | 'authenticated' | 'role-scoped';
export type RouteEntry = 'menu' | 'contextual' | 'direct' | 'callback' | 'internal';

// ============================================================================
// Route nav metadata (sidebar / menu / breadcrumb)
// ============================================================================

export interface RouteNav {
  label: string;
  icon: string;
  section: string;
  order: number;
  menu?: string;
  sidebar?: string;
}

// ============================================================================
// Route layout hints (consumed by AppShell)
// ============================================================================

export interface RouteLayout {
  hideHeader?: boolean;
  hideSidebar?: boolean;
  fullscreen?: boolean;
  sidebarPreset?: string;
  activeSidebarItem?: string;
  pageTitle: string;
}

// ============================================================================
// Route config — the canonical shape of each entry in routeRegistry.
// ⚠️ `component` is a string (lazy-import key), not a React component —
// the registry is a static data file, actual component resolution happens
// in AppRouter via React.lazy().
// ============================================================================

export interface RouteConfig {
  id: string;
  path: string;
  group: RouteGroup;
  surface: RouteSurface;
  lifecycle: RouteLifecycle;
  shell: RouteShell;
  auth: RouteAuth;
  roles: BackendRole[];
  homeForRoles?: FrontendRoleKey[];
  entry: RouteEntry;
  nav: false | RouteNav;
  title: string;
  owner: string;
  component: string;
  legacyRedirectFrom: string[];
  layout: RouteLayout;
}

/**
 * The route registry is exported as `RouteConfig[]`.
 * Type alias for clarity at call sites.
 */
export type RouteRegistry = RouteConfig[];
