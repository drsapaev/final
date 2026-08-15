// Ambient declarations for Node-side config files covered by tsconfig.node.json.
// Unlike src/types/declarations.d.ts (packages that ship no types), this shim
// covers a package that is deliberately NOT installed: @sentry/vite-plugin is
// an opt-in dependency loaded via dynamic import in vite.config.ts (see the
// comment block there). The shim only describes the used surface.
declare module '@sentry/vite-plugin' {
  export interface SentryVitePluginOptions {
    org?: string | undefined;
    project?: string | undefined;
    authToken?: string | undefined;
    release?: { name?: string | undefined } | undefined;
    applicationKey?: string | undefined;
    [key: string]: unknown;
  }
  export function sentryVitePlugin(options?: SentryVitePluginOptions): import('vite').Plugin;
}
