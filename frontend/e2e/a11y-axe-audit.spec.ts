// @ts-check
/**
 * a11y axe audit — PR-UI-18 item 4 (plan §PR-UI-18): integrate
 * @axe-core/playwright into the e2e suite and gate accessibility
 * regressions on public surfaces.
 *
 * Scope: 6 public routes × 2 themes (light/dark) = 12 audits.
 *   landing /, /login, /display-board, /queue/join,
 *   /payment/success, /payment/cancel
 *
 * Determinism contract (mirrors the pr18 baseline contract in
 * visual-regression.spec.ts — proven stable in CI):
 *   - Theme pinned via localStorage colorScheme/theme/ui_theme before load
 *     (colorScheme key has precedence, see theme/colorScheme.ts) and
 *     verified through the body[data-theme] contract.
 *   - Public API mocks: setup/status=initialized, auth/me=401, generic
 *     success envelope for the rest, WebSocket closed — deterministic
 *     states, no backend.
 *   - a11y analysis is DOM/computed-style based: animations and live clocks
 *     do not affect axe results; no clock freezing needed.
 *
 * Gate policy (ratchet, mirrors scripts/audit-icon-only-controls.mjs):
 *   - Baseline JSON at e2e/a11y-baseline.json maps route×theme → sorted
 *     list of accepted violation rule IDs (pre-existing findings, tracked
 *     for follow-up remediation).
 *   - The gate fails on any NEW violation rule that is not in the baseline,
 *     and on baseline entries that no longer reproduce (stale — baseline
 *     must shrink, not rot; shrinking is allowed and welcome).
 *   - FORBIDDEN: adding a rule to the baseline to make a failing audit pass
 *     without a documented justification (Rule 13 analog).
 *
 * E2E coverage invariant: this file runs fully — no test.skip/test.fixme.
 */
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const A11Y_ROUTES = [
  { path: '/', name: 'landing' },
  { path: '/login', name: 'login' },
  { path: '/display-board', name: 'display-board' },
  { path: '/queue/join', name: 'queue-join' },
  { path: '/payment/success', name: 'payment-success' },
  { path: '/payment/cancel', name: 'payment-cancel' },
] as const;

const THEMES = ['light', 'dark'] as const;

/** WCAG 2.0/2.1 A+AA rules — the project a11y bar (audit:a11y eslint
 * jsx-a11y rules operate at the same level for source code). */
const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

const BASELINE_PATH = resolve(__dirname, 'a11y-baseline.json');

function loadBaseline(): Record<string, string[]> {
  if (!existsSync(BASELINE_PATH)) return {};
  return JSON.parse(readFileSync(BASELINE_PATH, 'utf-8'));
}

async function pinTheme(page: import('@playwright/test').Page, mode: 'light' | 'dark') {
  await page.addInitScript((m) => {
    localStorage.setItem('colorScheme', m);
    localStorage.setItem('theme', m);
    localStorage.setItem('ui_theme', m);
  }, mode);
}

function jsonResponse(body: unknown): { status: number; contentType: string; body: string } {
  return { status: 200, contentType: 'application/json; charset=utf-8', body: JSON.stringify(body) };
}

async function installPublicApiMocks(page: import('@playwright/test').Page) {
  // Mock WebSocket to prevent ECONNREFUSED noise (no backend in E2E).
  await page.routeWebSocket('**/*', ws => { ws.close(); });
  await page.route('**/api/v1/**', async (route) => {
    const { pathname } = new URL(route.request().url());
    if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
    if (pathname === '/api/v1/auth/me') {
      await route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'not authenticated' }) });
      return;
    }
    if (pathname === '/api/v1/notifications/history/stats') { await route.fulfill(jsonResponse({ recent_activity: [] })); return; }
    await route.fulfill(jsonResponse({ success: true }));
  });
}

test.describe('a11y axe audit — PR-UI-18 item 4 · public surfaces × light/dark', () => {
  const baseline = loadBaseline();

  for (const route of A11Y_ROUTES) {
    for (const theme of THEMES) {
      const key = `${route.name}:${theme}`;

      test(`${key} — no new axe violations (WCAG 2.x A/AA)`, async ({ page }) => {
        await pinTheme(page, theme);
        await installPublicApiMocks(page);
        await page.goto(route.path, { waitUntil: 'domcontentloaded' });

        // Mounted app contract (mirrors frontend-10-visual-a11y).
        await expect(page.locator('#root')).toBeVisible();
        await expect.poll(
          async () => (await page.locator('body').innerText()).trim().length,
          { message: `${key}: route should render non-empty body text` }
        ).toBeGreaterThan(0);

        // Theme contract: body[data-theme] must reflect the pinned mode.
        await expect.poll(
          async () => page.evaluate(() => document.body.getAttribute('data-theme')),
          { message: `${key}: body[data-theme="${theme}"] must be applied before audit` }
        ).toBe(theme);

        // Bounded settle for async paint (pages that poll never reach
        // networkidle; a11y analysis itself is state-independent).
        await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => undefined);
        await page.waitForTimeout(300);

        const results = await new AxeBuilder({ page })
          .withTags(AXE_TAGS)
          .analyze();

        const actual = [...new Set(results.violations.map(v => v.id))].sort();
        const accepted = [...new Set(baseline[key] ?? [])].sort();

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
          `${key}: NEW a11y violations beyond the accepted baseline — fix the violation or document an explicit justification before adding it to e2e/a11y-baseline.json: ${newViolations.join(', ')}`
        ).toEqual([]);
        expect(
          stale,
          `${key}: baseline entries no longer reproduce — shrink e2e/a11y-baseline.json (stale: ${stale.join(', ')}); baseline must not rot`
        ).toEqual([]);
      });
    }
  }
});
