// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { ROUTE_REGISTRY, ROLE_HOME_PRIORITY, SIDEBAR_PRESETS } from './routeRegistry.js';

export function buildRouteDocsSnapshot() {
  const canonicalRoutes = ROUTE_REGISTRY;
  const aliases = canonicalRoutes.flatMap((route) =>
    (route.legacyRedirectFrom || []).map((aliasPath) => ({
      aliasPath,
      canonicalPath: route.path,
      routeId: route.id,
    }))
  );

  return {
    routeCount: canonicalRoutes.length,
    groups: canonicalRoutes.reduce((acc, route) => {
      acc[route.group] ||= [];
      acc[route.group].push({
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
    setupPolicy: [
      'callback/public technical routes remain available before initialization',
      'when not initialized, clinical and admin routes redirect to /setup',
      'when initialized, /setup redirects to /login',
      'login and setup must not loop',
    ],
    errorRoutes: ['/unauthorized', '/forbidden', '/not-found'],
  };
}

export function renderRouteDocsMarkdown(snapshot = buildRouteDocsSnapshot()) {
  const groupSections = Object.entries(snapshot.groups)
    .map(([group, routes]) => {
      const rows = routes
        .map((route) => `| \`${route.path}\` | \`${route.id}\` | ${route.title} | ${route.auth} | ${route.roles.join(', ') || 'public'} | ${route.lifecycle} |`)
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
