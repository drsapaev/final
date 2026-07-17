import { ROUTE_REGISTRY, ROLE_HOME_PRIORITY, SIDEBAR_PRESETS } from './routeRegistry.js';

// routeRegistry.ts is a literal array without explicit types. Model the
// canonical surface here so the snapshot generator can compile without
// @ts-nocheck. When routeRegistry.ts is migrated, these can move there.
type RouteGroup = 'public' | 'onboarding' | 'clinical' | 'admin' | 'internal-demo' | string;
type RouteAuth = 'public' | 'authenticated' | 'role-scoped' | string;
type RouteLifecycle = 'stable' | 'compatibility' | 'experimental' | 'internal' | string;
type RouteEntry = 'menu' | 'contextual' | 'direct' | 'callback' | 'internal' | string;

interface RouteRegistryEntry {
  id: string;
  path: string;
  group: RouteGroup;
  surface?: string;
  lifecycle?: RouteLifecycle;
  shell?: string;
  auth: RouteAuth;
  roles: string[];
  entry?: RouteEntry;
  nav?: boolean;
  title: string;
  owner?: string;
  component?: string;
  legacyRedirectFrom?: string[];
  layout?: Record<string, unknown>;
  [key: string]: unknown;
}

interface RouteAlias {
  aliasPath: string;
  canonicalPath: string;
  routeId: string;
}

interface RouteGroupSummary {
  id: string;
  path: string;
  title: string;
  auth: RouteAuth;
  roles: string[];
  lifecycle?: RouteLifecycle;
  entry?: RouteEntry;
}

export interface RouteDocsSnapshot {
  routeCount: number;
  groups: Record<string, RouteGroupSummary[]>;
  aliases: RouteAlias[];
  roleHomePriority: typeof ROLE_HOME_PRIORITY;
  sidebarPresets: string[];
  setupPolicy: string[];
  errorRoutes: string[];
}

const SETUP_POLICY: string[] = [
  'callback/public technical routes remain available before initialization',
  'when not initialized, clinical and admin routes redirect to /setup',
  'when initialized, /setup redirects to /login',
  'login and setup must not loop',
];

const ERROR_ROUTES: string[] = ['/unauthorized', '/forbidden', '/not-found'];

export function buildRouteDocsSnapshot(): RouteDocsSnapshot {
  const canonicalRoutes = ROUTE_REGISTRY as RouteRegistryEntry[];
  const aliases: RouteAlias[] = canonicalRoutes.flatMap((route) =>
    (route.legacyRedirectFrom || []).map((aliasPath) => ({
      aliasPath,
      canonicalPath: route.path,
      routeId: route.id,
    }))
  );

  return {
    routeCount: canonicalRoutes.length,
    groups: canonicalRoutes.reduce<Record<string, RouteGroupSummary[]>>((acc, route) => {
      const group = route.group;
      if (!acc[group]) {
        acc[group] = [];
      }
      acc[group].push({
        id: route.id,
        path: route.path,
        title: route.title,
        auth: route.auth,
        roles: route.roles,
        lifecycle: route.lifecycle,
        entry: route.entry,
      });
      return acc;
    }, {}),
    aliases,
    roleHomePriority: ROLE_HOME_PRIORITY,
    sidebarPresets: Object.keys(SIDEBAR_PRESETS),
    setupPolicy: SETUP_POLICY,
    errorRoutes: ERROR_ROUTES,
  };
}

export function renderRouteDocsMarkdown(snapshot: RouteDocsSnapshot = buildRouteDocsSnapshot()): string {
  const groupSections = Object.entries(snapshot.groups)
    .map(([group, routes]) => {
      const rows = routes
        .map((route) => `| \`${route.path}\` | \`${route.id}\` | ${route.title} | ${route.auth} | ${route.roles.join(', ') || 'public'} | ${route.lifecycle ?? ''} |`)
        .join('\n');
      return `## ${group}\n\n| Path | Id | Title | Auth | Roles | Lifecycle |\n|---|---|---|---|---|---|\n${rows}`;
    })
    .join('\n\n');

  const aliasRows = snapshot.aliases.length
    ? snapshot.aliases
      .map((alias) => `| \`${alias.aliasPath}\` | \`${alias.canonicalPath}\` | \`${alias.routeId}\` |`)
      .join('\n')
    : '| None | None | None |';

  return `# Routing Contract Snapshot

This document is derived from the frontend route registry.

${groupSections}

## Compatibility Redirects

| Legacy Path | Canonical Path | Route Id |
|---|---|---|
${aliasRows}

## Setup Gating

${snapshot.setupPolicy.map((line) => `- ${line}`).join('\n')}

## Error Routes

${snapshot.errorRoutes.map((route) => `- \`${route}\``).join('\n')}
`;
}
