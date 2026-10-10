import { defineConfig } from 'nitro';

const productionDomain = process.env.VERCEL_PROJECT_PRODUCTION_URL;

export default defineConfig({
  // Public routes need direct route handlers: Nitro server-entry middleware
  // treats a 404 Response as fallthrough to the SPA renderer.
  serverEntry: false,
  handlers: [
    '/',
    '/ru',
    '/services',
    '/services/:slug',
    '/doctors',
    '/doctors/:slug',
    '/prices',
    '/contacts',
    '/ru/services',
    '/ru/services/:slug',
    '/ru/doctors',
    '/ru/doctors/:slug',
    '/ru/prices',
    '/ru/contacts',
    '/robots.txt',
    '/sitemap.xml',
    '/api',
    '/api/**',
    '/ws',
    '/ws/**',
  ].map((route) => ({ route, handler: './src/publicSiteHandler.tsx', format: 'web' as const })),
  runtimeConfig: {
    apiOrigin: '',
    siteOrigin: productionDomain ? `https://${productionDomain}` : '',
    deploymentEnvironment: process.env.VERCEL_ENV || 'development',
  },
});
