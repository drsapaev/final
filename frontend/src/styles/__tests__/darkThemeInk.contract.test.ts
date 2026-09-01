import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * CC-1 (UI color-contrast track, §4.1.18 follow-up): dark-mode ink restoration.
 *
 * The legacy `src/styles/dark-theme-visibility-fix.css` used to force
 * `color: var(--dark-text-primary) !important` (= --mac-bg-secondary = #2c2c2e,
 * a BACKGROUND value used as TEXT ink) onto every button in classic dark mode,
 * plus `button * { color: inherit !important }`. The paired background-color
 * declaration carried no !important, so canonical mac-buttons kept their inline
 * variant backgrounds (blue / transparent / dark tint) while losing their text
 * color to a dark gray — labels rendered at 1.04–3.47:1 across the whole app
 * in dark mode (axe color-contrast, e2e/a11y-baseline.json, PR-UI-18 item 4).
 *
 * This contract pins the decommission so the rules cannot silently come back.
 */
const visibilityFixPath = path.resolve(__dirname, '../dark-theme-visibility-fix.css');
const tokensPath = path.resolve(__dirname, '../../design-system/tokens.css');

const readVisibilityFix = () =>
  // Strip /* ... */ comments first — the decommission note itself describes the
  // removed rules verbatim and must not trip the selectors-below matchers.
  fs.readFileSync(visibilityFixPath, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
const readTokens = () =>
  fs.readFileSync(tokensPath, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');

describe('dark-theme-visibility-fix.css — CC-1 button-ink decommission contract', () => {
  /** Split a stylesheet into { selector, body } rule pairs (comments stripped). */
  const parseRules = (css: string) =>
    (css.match(/[^{}]+\{[^}]*\}/g) ?? [])
      .map((rule) => {
        const brace = rule.indexOf('{');
        return { selector: rule.slice(0, brace).trim(), body: rule.slice(brace) };
      })
      .filter(({ selector }) => selector.length > 0 && !selector.startsWith('@'));

  /** True when the selector targets the bare `button` ELEMENT (not a class
   * like .button-secondary — those hit legacy components with paired
   * background !important and are out of this contract's scope). */
  const targetsButtonElement = (selector: string) =>
    selector
      .split(',')
      .some((part) => /(^|[\s>+~])button(?![\w-])/.test(part) || /(^|[\s>+~])button\s*\*/.test(part));

  it('does not force a text color onto buttons with !important', () => {
    const css = readVisibilityFix();
    // `color: inherit !important` scoped to a parent (e.g. .app-header-2025)
    // is semantically different: it keeps the parent's readable ink instead
    // of forcing a broken one. Only FORCED color values are the CC-1 bug class.
    const matches = parseRules(css)
      .filter(
        ({ selector, body }) =>
          targetsButtonElement(selector) &&
          /color:[^;}]*!important/.test(body) &&
          !/color:\s*inherit[^;}]*!important/.test(body)
      )
      .map(({ selector }) => selector);
    expect(
      matches,
      'element-level button selectors with a forced color !important must stay decommissioned (CC-1): ' +
        'they override canonical Button variant inline styles and render labels at 1.04–3.47:1 in dark mode'
    ).toEqual([]);
  });

  it('does not force color inheritance onto button descendants', () => {
    const css = readVisibilityFix();
    const matches = parseRules(css)
      .filter(
        ({ selector, body }) =>
          /button\s*\*/.test(selector) && /color:\s*inherit[^;}]*!important/.test(body)
      )
      .map(({ selector }) => selector);
    expect(
      matches,
      'button * { color: inherit !important } must stay decommissioned (CC-1): ' +
        'it pinned icon and label colors inside buttons to the forced dark ink'
    ).toEqual([]);
  });

  it('still pairs background and text !important on the legacy surfaces it patches', () => {
    // The REMAINING rules in the file are load-bearing for legacy surfaces and
    // must keep declaring background together with color (both !important) —
    // an unpaired color !important is exactly the class of bug CC-1 removed.
    const css = readVisibilityFix();
    const ruleBodies = css.match(/\{[^}]*\}/g) ?? [];
    const unpaired = ruleBodies.filter((body) => {
      const hasImportantColor = /color:[^;}]*!important/.test(body);
      const hasImportantBackground =
        /(?:^|[^-])(?:background(?:-color)?|border)[^;:]*:[^;}]*!important/.test(body) ||
        /border-color:[^;}]*!important/.test(body);
      return hasImportantColor && !hasImportantBackground;
    });
    expect(
      unpaired,
      'every color !important declaration must stay paired with a background/border !important ' +
        '(unpaired declarations recreate the CC-1 ink/background mismatch)'
    ).toEqual([]);
  });
});

describe('tokens.css — CC-1 dark secondary-ink contrast contract', () => {
  it('dark --mac-text-secondary meets WCAG AA (≥4.5:1) on --mac-bg-content #2c2c2e', () => {
    const css = readTokens();
    // Both dark blocks (the prefers-color-scheme :root block and the explicit
    // .dark-theme block) must define the contrast-safe muted ink — #8e8e93
    // measured 4.27:1 on the dark shell background. The high-contrast media
    // block (#000000) and the light blocks are out of scope here.
    const darkThemeBlock = css.match(/\.dark-theme\s*\{[\s\S]*?\}/)?.[0] ?? '';
    const darkMediaBlock =
      css.match(/@media\s*\(prefers-color-scheme:\s*dark\)\s*\{[\s\S]*?\n\s*\}/)?.[0] ?? '';
    const extract = (block: string) =>
      block.match(/--mac-text-secondary:\s*(#[0-9a-fA-F]{6});/)?.[1]?.toLowerCase() ?? null;

    const darkValues = [extract(darkThemeBlock), extract(darkMediaBlock)];
    expect(darkValues.every(Boolean), 'both dark blocks must define --mac-text-secondary').toBe(true);

    const luminance = (hex: string) => {
      const n = hex.slice(1).match(/.{2}/g)!.map((b) => parseInt(b, 16) / 255);
      const lin = n.map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
      return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
    };
    const ratio = (fg: string, bg: string) => {
      const l1 = luminance(fg);
      const l2 = luminance(bg);
      const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
      return (hi + 0.05) / (lo + 0.05);
    };

    for (const value of darkValues as string[]) {
      expect(
        ratio(value, '#2c2c2e'),
        `dark --mac-text-secondary ${value} must stay ≥ 4.5:1 on --mac-bg-content #2c2c2e (CC-1)`
      ).toBeGreaterThanOrEqual(4.5);
    }
  });
});
