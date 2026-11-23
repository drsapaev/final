import React from 'react';
import '@testing-library/jest-dom';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import fs from 'fs';
import path from 'path';
import userEvent from '@testing-library/user-event';

/**
 * EMRREAD-FE-001 + EMRCOLLAPSE-FE-001 (audit 3886, round 21) — fail-first.
 *
 * EMRREAD-FE-001: `.emr-section--disabled` applied `pointer-events:none` to the
 * WHOLE section subtree, including the expansion button, so a signed/completed
 * (read-only) EMR could not be expanded by mouse or touch. The fix keeps the
 * header interactive and scopes pointer-events to the section BODY only.
 *
 * EMRCOLLAPSE-FE-001: the collapsed body stayed mounted-and-focusable (only
 * grid-template-rows:0fr hid it visually), so Tab moved focus into invisible
 * fields and screen readers announced collapsed content. The fix wires
 * aria-controls + a stable body id and applies inert/aria-hidden to the
 * collapsed body.
 *
 * jsdom does not enforce CSS pointer-events or inert focus-blocking, so the
 * mechanism is pinned BOTH behaviorally (header toggles while disabled) and by
 * a source contract on the CSS scoping (repo precedent for container tests).
 */

import EMRSectionRaw from '../EMRSection';

const EMRSection = EMRSectionRaw as unknown as React.ComponentType<Record<string, unknown>>;

describe('EMRCOLLAPSE-FE-001: collapsed body is removed from the a11y tree and tab order', () => {
  it('marks the collapsed body inert + aria-hidden and re-exposes it on expand', () => {
    const { container } = render(
      <EMRSection title="Лечение" defaultOpen={false}>
        <input aria-label="treatment-input" />
      </EMRSection>
    );
    const body = container.querySelector('.emr-section__body') as HTMLElement;
    const header = container.querySelector('.emr-section__header') as HTMLElement;

    expect(body).not.toBeNull();
    expect(header).not.toBeNull();

    // collapsed → hidden from assistive tech and unreachable by Tab
    expect(body.hasAttribute('inert')).toBe(true);
    expect(body.getAttribute('aria-hidden')).toBe('true');

    // the toggle is programmatically linked to the body it controls
    expect(header.getAttribute('aria-controls')).toBe(body.id);
    expect(body.id).toBeTruthy();

    // expand → a11y-visible again
    fireEvent.click(header);
    expect(body.hasAttribute('inert')).toBe(false);
    expect(body.getAttribute('aria-hidden')).toBe('false');
    expect(header.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByLabelText('treatment-input')).toBeInTheDocument();
  });

  it('re-hides the body (inert + aria-hidden) when collapsing back', () => {
    const { container } = render(
      <EMRSection title="Рекомендации" defaultOpen={true}>
        <input aria-label="recs-input" />
      </EMRSection>
    );
    const body = container.querySelector('.emr-section__body') as HTMLElement;
    const header = container.querySelector('.emr-section__header') as HTMLElement;
    expect(body.hasAttribute('inert')).toBe(false);

    fireEvent.click(header); // collapse
    expect(body.hasAttribute('inert')).toBe(true);
    expect(body.getAttribute('aria-hidden')).toBe('true');
    expect(header.getAttribute('aria-expanded')).toBe('false');
  });

  it('supports keyboard activation of the toggle (Enter)', async () => {
    const user = userEvent.setup();
    const { container } = render(
      <EMRSection title="Осмотр" defaultOpen={false}>
        <input aria-label="exam-input" />
      </EMRSection>
    );
    const header = container.querySelector('.emr-section__header') as HTMLElement;
    const body = container.querySelector('.emr-section__body') as HTMLElement;
    header.focus();
    await user.keyboard('{Enter}');
    expect(header.getAttribute('aria-expanded')).toBe('true');
    expect(body.hasAttribute('inert')).toBe(false);
  });
});

describe('EMRREAD-FE-001: read-only sections remain expandable', () => {
  it('expands a disabled section by pointer while the disabled class is present', () => {
    const { container } = render(
      <EMRSection title="Лечение" disabled defaultOpen={false}>
        <input aria-label="inner-field" />
      </EMRSection>
    );
    const section = container.querySelector('.emr-section') as HTMLElement;
    const header = container.querySelector('.emr-section__header') as HTMLElement;
    const body = container.querySelector('.emr-section__body') as HTMLElement;

    // the section is visually marked read-only…
    expect(section.className).toContain('emr-section--disabled');
    // …but the expansion toggle still works (pre-fix: pointer-events:none on the
    // whole subtree made this click dead in a real browser)
    expect(header.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(header);
    expect(header.getAttribute('aria-expanded')).toBe('true');
    expect(body.className).toContain('emr-section__body--open');
    expect(screen.getByLabelText('inner-field')).toBeInTheDocument();
  });

  it('keyboard expansion also works on a disabled section', async () => {
    const user = userEvent.setup();
    const { container } = render(
      <EMRSection title="Заметки" disabled defaultOpen={false}>
        <input aria-label="notes-field" />
      </EMRSection>
    );
    const header = container.querySelector('.emr-section__header') as HTMLElement;
    header.focus();
    await user.keyboard('{Enter}');
    expect(header.getAttribute('aria-expanded')).toBe('true');
  });

  // Source contract (repo precedent): jsdom cannot enforce CSS pointer-events,
  // so pin the mechanism itself — the section ROOT must no longer carry
  // pointer-events:none; only the BODY (clinical inputs) is shielded.
  it('CSS: pointer-events:none is scoped to the section body, not the section root', () => {
    const css = fs.readFileSync(path.join(__dirname, '..', 'EMRSection.css'), 'utf-8');
    const rootRule = css.match(/\.emr-section--disabled\s*\{[^}]*\}/)?.[0] ?? '';
    expect(rootRule).not.toMatch(/pointer-events/);
    expect(css).toMatch(
      /\.emr-section--disabled\s+\.emr-section__body\s*\{[^}]*pointer-events:\s*none[^}]*\}/
    );
  });
});
