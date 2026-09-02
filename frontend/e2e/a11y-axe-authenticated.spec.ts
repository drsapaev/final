// @ts-check
/**
 * a11y axe audit — AUTHORIZED QA-harness surfaces (AXE-EXP-1, follow-up
 * track candidate from plan §4.1.24): extend the PR-UI-18 item 4 a11y
 * gate from 6 public routes to the authenticated role/specialty/admin
 * surfaces reachable through the QA harness
 * (e2e/support/authenticatedQa.ts).
 *
 * Scope: 17 authorized routes × 2 themes (light/dark) = 34 audits.
 *   role homes:    /admin /registrar /doctor /cashier /lab /patient
 *   specialty:     /doctor/cardiology?tab=appointments
 *                  /doctor/dermatology?tab=appointments
 *   admin family:  /admin/users /admin/services /admin/appointments
 *                  /admin/system /admin/webhooks /admin/integrations/telegram
 *                  /admin/notifications /admin/finance
 *                  /admin/clinic-settings?section=clinic-settings
 *
 * Determinism contract (mirrors a11y-axe-audit.spec.ts — proven stable
 * in CI — plus the pr18 QA-harness baselines in visual-regression.spec.ts):
 *   - Auth via installAuthenticatedQaHarness (mock JWT + sessionStorage
 *     seed + generic API envelope mocks; no backend).
 *   - Theme pinned via localStorage colorScheme/theme/ui_theme registered
 *     AFTER the harness init script (colorScheme has precedence over the
 *     harness's theme=light pin — theme/colorScheme.ts:188; same
 *     pinning contract as visual-regression.spec.ts) and verified through
 *     the body[data-theme] contract.
 *   - WebSocket closed (routeWebSocket) — same as the pr18 baselines.
 *   - Deterministic settle: DOM-stability poll (two consecutive identical
 *     DOM signatures 250ms apart, 8s budget). Empirically required: some
 *     authorized surfaces oscillate during async mock-data loading (e.g.
 *     /admin/webhooks renders its role=tab buttons → drops them on the
 *     error state → re-renders them ~2.5s later); auditing a transient
 *     state made aria-valid-attr-value findings flaky. Pages with
 *     perpetual small DOM updates (clocks) exhaust the budget and audit
 *     whatever is rendered — axe analysis itself is state-independent.
 *   - a11y analysis is DOM/computed-style based: animations and live
 *     clocks do not affect axe results; no clock freezing needed.
 *
 * Gate policy (ratchet, mirrors a11y-axe-audit.spec.ts):
 *   - Baseline JSON at e2e/a11y-baseline-auth.json maps route:theme →
 *     sorted list of accepted violation rule IDs. It is seeded with the
 *     PRE-EXISTING findings discovered by the AXE-EXP probe (main
 *     aca7d96a8, 02.09.2026, two consecutive probe runs) so the gate is
 *     enforceable from day one; remediation increments must SHRINK it.
 *   - The gate fails on any NEW violation rule that is not in the
 *     baseline, and on baseline entries that no longer reproduce (stale
 *     — baseline must shrink, not rot).
 *   - FORBIDDEN: adding a rule to the baseline to make a failing audit
 *     pass without a documented justification (Rule 13 analog).
 *
 * Diagnostics: A11Y_AUTH_DUMP=<path> env var dumps one NDJSON line per
 * audit (actual rule IDs + node counts) for baseline re-seeding during
 * remediation increments — the gate itself never depends on it.
 *
 * E2E coverage invariant: this file runs fully — no
 * test.skip/test.fixme.
 */
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync, existsSync, appendFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  AUTHENTICATED_ROLE_QA_ROUTES,
  AUTHENTICATED_SPECIALTY_QA_ROUTES,
  installAuthenticatedQaHarness,
} from './support/authenticatedQa';
import type { Page } from '@playwright/test';
import type { RoleQaRoute, SpecialtyQaRoute } from './support/authenticatedQa';

const __dirname = dirname(fileURLToPath(import.meta.url));

/**
 * Admin route family — mirrors the QA-harness admin-family coverage of
 * authenticated-role-smoke.spec.ts (route names aligned with its keys;
 * path/query identical; routeId from routeRegistry.ts).
 */
const ADMIN_FAMILY_QA_ROUTES = [
  { key: 'admin-users', role: 'Admin', path: '/admin/users', routeId: 'admin-users' },
  { key: 'admin-services', role: 'Admin', path: '/admin/services', routeId: 'admin-services' },
  { key: 'admin-appointments', role: 'Admin', path: '/admin/appointments', routeId: 'admin-appointments' },
  { key: 'admin-system', role: 'Admin', path: '/admin/system', routeId: 'admin-system' },
  { key: 'admin-webhooks', role: 'Admin', path: '/admin/webhooks', routeId: 'admin-webhooks' },
  { key: 'admin-telegram', role: 'Admin', path: '/admin/integrations/telegram', routeId: 'admin-telegram-integration' },
  { key: 'admin-notifications', role: 'Admin', path: '/admin/notifications', routeId: 'admin-notifications' },
  { key: 'admin-finance', role: 'Admin', path: '/admin/finance', routeId: 'admin-finance' },
  { key: 'admin-clinic-settings', role: 'Admin', path: '/admin/clinic-settings?section=clinic-settings', routeId: 'admin-clinic-settings' },
] as const;

interface AuthQaRoute {
  key: string;
  role: string;
  path: string;
  routeId: string;
}

const AUTH_QA_ROUTES: AuthQaRoute[] = [
  ...AUTHENTICATED_ROLE_QA_ROUTES.map(
    (r: RoleQaRoute): AuthQaRoute => ({ key: r.key, role: r.role, path: r.path, routeId: r.routeId })
  ),
  ...AUTHENTICATED_SPECIALTY_QA_ROUTES.map(
    (r: SpecialtyQaRoute): AuthQaRoute => ({ key: r.key, role: r.role, path: r.path, routeId: r.routeId })
  ),
  ...ADMIN_FAMILY_QA_ROUTES.map(
    (r: { key: string; role: string; path: string; routeId: string }): AuthQaRoute => ({ ...r })
  ),
];

const THEMES = ['light', 'dark'] as const;

/** WCAG 2.0/2.1 A+AA rules — the project a11y bar (same tags as
 * a11y-axe-audit.spec.ts; audit:a11y eslint jsx-a11y rules operate at
 * the same level for source code). */
const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

const BASELINE_PATH = resolve(__dirname, 'a11y-baseline-auth.json');

/** Optional NDJSON dump of actual findings (baseline re-seeding tool). */
const DUMP_PATH = process.env.A11Y_AUTH_DUMP || '';

/** DOM signature for the stability settle: outerHTML length + counts of
 * the element kinds that oscillate during async role/tab mounting + the
 * computed html ink/background (covers the 300ms background transition
 * and detects late-arriving stylesheets; the themed background lives on
 * <html>, body stays transparent). */
async function domSignature(page: Page): Promise<string> {
  return page.evaluate(() => {
    const tabs = document.querySelectorAll('[role="tab"]').length;
    const controlled = document.querySelectorAll('[aria-controls]').length;
    const forms = document.querySelectorAll('input, select, textarea').length;
    const htmlStyle = getComputedStyle(document.documentElement);
    return `${document.body.outerHTML.length}:${tabs}:${controlled}:${forms}:${htmlStyle.backgroundColor}:${htmlStyle.color}`;
  });
}

/** Deterministic settle: audit only a DOM that stopped changing.
 * Minimum floor of 1500ms, then four consecutive identical signatures
 * (250ms apart = 1000ms of stability); 8s budget; on timeout audit the
 * current DOM (bounded, same as a fixed wait). The content-mount contract
 * (main region text) must pass BEFORE this — under heavy parallel load
 * React can pause >750ms mid-mount with the shell stable but the main
 * region empty, and stability alone would audit that partial state
 * (empirically: pass=14 vs 23-28 rules, false-clean results). */
async function settleForAudit(page: Page) {
  const intervalMs = 250;
  const budgetMs = 8000;
  const floorMs = 1500;
  const startedAt = Date.now();
  const deadline = startedAt + budgetMs;
  let lastSig = '';
  let stableHits = 0;
  while (Date.now() < deadline) {
    await page.waitForTimeout(intervalMs);
    const sig = await domSignature(page);
    if (Date.now() - startedAt >= floorMs && sig === lastSig) {
      stableHits++;
      if (stableHits >= 4) return;
    } else {
      stableHits = 0;
    }
    lastSig = sig;
  }
}

function loadBaseline(): Record<string, string[]> {
  if (!existsSync(BASELINE_PATH)) return {};
  const parsed = JSON.parse(readFileSync(BASELINE_PATH, 'utf-8'));
  const out: Record<string, string[]> = {};
  for (const [key, value] of Object.entries(parsed)) {
    if (key === '_meta' || !Array.isArray(value)) continue;
    out[key] = value as string[];
  }
  return out;
}

async function pinTheme(page: Page, mode: 'light' | 'dark') {
  // Registered AFTER installAuthenticatedQaHarness so this init script
  // runs after the harness's own script; colorScheme has precedence in
  // resolveThemeMode (theme/colorScheme.ts) — same contract as the
  // visual-regression pr18 theme pinning.
  await page.addInitScript((m) => {
    localStorage.setItem('colorScheme', m);
    localStorage.setItem('theme', m);
    localStorage.setItem('ui_theme', m);
  }, mode);
}

test.describe('a11y axe audit — AXE-EXP-1 · authorized QA-harness surfaces × light/dark', () => {
  const baseline = loadBaseline();

  for (const route of AUTH_QA_ROUTES) {
    for (const theme of THEMES) {
      const key = `${route.key}:${theme}`;

      test(`${key} — no new axe violations (WCAG 2.x A/AA)`, async ({ page }) => {
        await page.routeWebSocket('**/*', ws => { ws.close(); });
        await installAuthenticatedQaHarness(page, { role: route.role });
        await pinTheme(page, theme);
        await page.goto(route.path, { waitUntil: 'domcontentloaded' });

        // Mounted app contract (mirrors the pr18 QA-harness baselines):
        // the ROUTE shell must be mounted — .app-shell[data-route-id] is
        // the pr18-proven marker that guards against auditing a partial
        // early mount under parallel load.
        await expect(page.locator('#root')).toBeVisible();
        await expect(
          page.locator(`.app-shell[data-route-id="${route.routeId}"]`)
        ).toBeVisible({ timeout: 15000 });
        await expect.poll(
          async () => (await page.locator('body').innerText()).trim().length,
          { timeout: 15000, message: `${key}: route should render non-empty body text` }
        ).toBeGreaterThan(0);

        // Theme contract: body[data-theme] must reflect the pinned mode.
        await expect.poll(
          async () => page.evaluate(() => document.body.getAttribute('data-theme')),
          { timeout: 10000, message: `${key}: body[data-theme="${theme}"] must be applied before audit` }
        ).toBe(theme);

        // Style-application contract: bootstrap CSS (globalStyles/tokens)
        // must be live BEFORE any audit — under heavy parallel load the
        // Vite dev server can serve stylesheets well after DOM mount, and
        // an unstyled DOM (default black-on-white) yields false "clean"
        // axe results (observed: fully-rendered page, 0 violations). The
        // themed background lives on <html> (light #eef3fa / dark
        // #1c1c1e — tokens.css); body itself stays transparent.
        await expect.poll(
          async () => page.evaluate(() => getComputedStyle(document.documentElement).backgroundColor),
          { timeout: 15000, message: `${key}: styles must be applied (html background resolved) before audit` }
        ).not.toBe('rgba(0, 0, 0, 0)');

        // Content-mount contract: the route CONTENT must be rendered, not
        // just the shell — under heavy parallel load React can pause
        // >750ms mid-mount with the shell stable and the main region
        // still empty; auditing that partial DOM yields false-clean
        // results. Every audited surface renders meaningful main text
        // (headings, toolbars, empty states) once mounted.
        await expect.poll(
          async () => {
            return page.evaluate(() => {
              const main = document.querySelector('.app-shell main, main');
              if (!main) return 0;
              return (main as HTMLElement).innerText.trim().length;
            });
          },
          { timeout: 15000, message: `${key}: route content (main region text) must be mounted before audit` }
        ).toBeGreaterThan(30);

        // Bounded settle: DOM-stability poll (see contract above) — audits
        // the quiescent state, not a transient async-loading state.
        await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => undefined);
        await settleForAudit(page);

        const results = await new AxeBuilder({ page })
          .withTags(AXE_TAGS)
          .analyze();

        const actual = [...new Set(results.violations.map(v => v.id))].sort();
        const accepted = [...new Set(baseline[key] ?? [])].sort();

        if (DUMP_PATH) {
          appendFileSync(DUMP_PATH, JSON.stringify({
            key,
            role: route.role,
            path: route.path,
            theme,
            violations: results.violations.map(({ id, nodes }) => ({
              id, nodeCount: nodes.length,
              selectors: nodes.slice(0, 5).map(n => n.target.join(' ')),
            })),
          }) + '\n');
        }

        const newViolations = actual.filter(id => !accepted.includes(id));
        const stale = accepted.filter(id => !actual.includes(id));

        // Diagnostic attachment: full violation context for triage.
        await test.info().attach(`${key} axe violations`, {
          body: JSON.stringify(
            results.violations.map(({ id, impact, help, nodes }) => ({
              id, impact, help, nodeCount: nodes.length,
              selectors: nodes.slice(0, 3).map(n => n.target.join(' ')),
            })),
            null,
            2,
          ),
          contentType: 'application/json',
        });

        expect(
          newViolations,
          `${key}: NEW a11y violations beyond the accepted baseline — fix the violation or document an explicit justification before adding it to e2e/a11y-baseline-auth.json: ${newViolations.join(', ')}`
        ).toEqual([]);
        expect(
          stale,
          `${key}: baseline entries no longer reproduce — shrink e2e/a11y-baseline-auth.json (stale: ${stale.join(', ')}); baseline must not rot`
        ).toEqual([]);
      });
    }
  }
});
