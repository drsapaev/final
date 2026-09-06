/**
 * AXE-MOB-1 (Mobile Chrome registrar:light/dark, axe button-name):
 * Tabs.css hides .tab-label at <=768px, collapsing every tab button into an
 * icon-only control with NO accessible name — axe flagged 7 button-name
 * violations on /registrar at the Pixel 5 viewport (light AND dark).
 *
 * The fix pins aria-label on both button kinds, sourced from the SAME
 * string as the visible label, so:
 *   - the name survives the mobile collapse (button-name satisfied), and
 *   - at desktop widths the accessible name stays identical to the visible
 *     label (WCAG 2.5.3 Label-in-Name).
 *
 * Rendering strategy: the api client mock REJECTS, so Tabs mounts its
 * hardcoded fallback department set (6 tabs) deterministically — no
 * backend in the loop (same pattern as UserModal.rolePayload.test.tsx,
 * where useTranslation is identity-mocked, so t(key) -> key).
 */
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../api/client', () => ({
  api: {
    get: vi.fn().mockRejectedValue(new Error('offline — fallback tabs expected')),
  },
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

import Tabs from '../Tabs';

afterEach(() => cleanup());

describe('Tabs — accessible names survive the mobile label collapse (AXE-MOB-1)', () => {
  it('all-departments button resolves an accessible name equal to its visible label source', async () => {
    render(<Tabs />);

    // findByRole computes the ACTUAL accessible name (aria-label) — this
    // both waits out the loading stub and proves the name resolves.
    const allDepartments = await screen.findByRole('button', {
      name: 'queue.all_departments',
    });

    expect(allDepartments).toHaveAttribute('aria-label', 'queue.all_departments');
    // Label-in-Name: visible label text matches the name source.
    expect(allDepartments.querySelector('.tab-label')?.textContent).toBe('queue.all_departments');
  });

  it('every department tab carries a non-empty aria-label equal to its visible label', async () => {
    render(<Tabs />);

    // Fallback set mounts after the mocked api rejection (6 departments).
    await waitFor(() => {
      expect(document.querySelectorAll('.tab-button.department').length).toBe(6);
    });

    const departmentButtons = Array.from(
      document.querySelectorAll<HTMLButtonElement>('.tab-button.department')
    );

    for (const button of departmentButtons) {
      const name = button.getAttribute('aria-label');
      expect(name).toBeTruthy();
      const visible = button.querySelector('.tab-label')?.textContent ?? '';
      expect(visible).not.toBe('');
      // Same source in both places -> byte-identical.
      expect(name).toBe(visible);
    }
  });

  // Codex P2 round 1 (thread 3944915764): aria-label overrides
  // name-from-content, so the status indicators (active queue, pending
  // payment, today count) must ride the accessible DESCRIPTION instead —
  // aria-describedby -> the in-button .status-indicators container, which
  // stays visible (referenceable) at every viewport width.
  // Codex P2 round 2 (thread 3944985044): the target must carry REAL
  // localized text (titles do not concatenate; boolean-only states would be
  // empty) — the .sr-only sentence is asserted via toHaveAccessibleDescription.
  it('populated departmentStats: status text is the button accessible description', async () => {
    render(
      <Tabs
        departmentStats={{
          cardiology: { todayCount: 4, hasActiveQueue: true, hasPendingPayments: true },
          ecg: { todayCount: 0, hasActiveQueue: true, hasPendingPayments: false },
        }}
      />
    );

    const cardiology = await screen.findByRole('button', { name: 'misc.mt_kardiolog' });

    const describedBy = cardiology.getAttribute('aria-describedby');
    expect(describedBy).toBeTruthy();

    // The reference resolves INSIDE the same button (no dangling id) and
    // targets the DEDICATED sr-only sentence node (round 2: the visible
    // indicator container would concatenate bare count digits into the
    // description).
    const statusTarget = document.getElementById(describedBy as string);
    expect(statusTarget).not.toBeNull();
    expect(cardiology.contains(statusTarget as Node)).toBe(true);
    expect(statusTarget).toHaveClass('sr-only');
    expect(statusTarget?.textContent).toBe(
      'final.tgs_active_queue, registrarPanel.pending_payments, registrarPanel.today: 4',
    );

    // Visible indicators render as before (pure visual layer); tooltips
    // agree with the description (round-4 semantics + i18n).
    const statusContainer = cardiology.querySelector('.status-indicators');
    expect(statusContainer!.querySelectorAll('.status-indicator').length).toBe(3);
    expect(statusContainer!.querySelector('.status-indicator.queue')).not.toBeNull();
    expect(statusContainer!.querySelector('.status-indicator.pending')).not.toBeNull();
    expect(statusContainer!.querySelector('.status-indicator.count')?.textContent).toContain('4');
    expect(statusContainer!.querySelector('.status-indicator.queue')).toHaveAttribute(
      'title',
      'final.tgs_active_queue',
    );
    expect(statusContainer!.querySelector('.status-indicator.pending')).toHaveAttribute(
      'title',
      'registrarPanel.pending_payments',
    );
    expect(statusContainer!.querySelector('.status-indicator.count')).toHaveAttribute(
      'title',
      'registrarPanel.today: 4',
    );

    // THE assertion Codex demanded: the computed accessible description
    // carries the full localized status text (active queue is a boolean
    // phrase WITHOUT the unrelated today-count).
    expect(cardiology).toHaveAccessibleDescription(
      'final.tgs_active_queue, registrarPanel.pending_payments, registrarPanel.today: 4',
    );

    // Boolean-only state (active queue, zero count): previously this would
    // compute an EMPTY description (icon SVG only) — now it announces text,
    // with NO misleading "queue size" number.
    const ecg = screen.getByRole('button', { name: 'misc.mt_ekg' });
    expect(ecg).toHaveAccessibleDescription('final.tgs_active_queue');
  });

  it('empty departmentStats: no aria-describedby dangles on department buttons', async () => {
    render(<Tabs />);

    await waitFor(() => {
      expect(document.querySelectorAll('.tab-button.department').length).toBe(6);
    });

    const departmentButtons = Array.from(
      document.querySelectorAll<HTMLButtonElement>('.tab-button.department')
    );
    for (const button of departmentButtons) {
      expect(button.getAttribute('aria-describedby')).toBeNull();
    }
  });

  // Codex P2 round 4 (thread 3945043230): "test against real locale
  // resources" — the three status keys must be DEFINED in every locale
  // file, in the exact namespaces the component references.
  // Codex P2 round 5 (thread 3945071007): the active-queue phrase must be
  // LOCALIZED — en/kk/uz-Cyrl previously carried the Russian text.
  it('status keys resolve in real locale resources for all five locales', () => {
    const fs = require('node:fs') as typeof import('node:fs');
    const path = require('node:path') as typeof import('node:path');

    const localesDir = path.resolve(__dirname, '../../../i18n/locales');

    const nsMemberValue = (src: string, ns: string, member: string): string | null => {
      const block = new RegExp(`^  ${ns}: \\{([\\s\\S]*?)^  \\},`, 'm').exec(src);
      if (!block) return null;
      const m = new RegExp(`^    ${member}: '(.*)',?$`, 'm').exec(block[1]);
      return m ? m[1] : null;
    };

    for (const locale of ['ru', 'en', 'kk', 'uz-Cyrl', 'uz-Latn']) {
      const src = fs.readFileSync(path.join(localesDir, `${locale}.ts`), 'utf8');
      expect(nsMemberValue(src, 'final', 'tgs_active_queue'), `${locale}: final.tgs_active_queue`).toBeTruthy();
      expect(
        nsMemberValue(src, 'registrarPanel', 'pending_payments'),
        `${locale}: registrarPanel.pending_payments`,
      ).toBeTruthy();
      expect(nsMemberValue(src, 'registrarPanel', 'today'), `${locale}: registrarPanel.today`).toBeTruthy();
    }

    // Localized (round-5): no more Russian "Активная очередь" outside ru.
    expect(nsMemberValue(fs.readFileSync(path.join(localesDir, 'ru.ts'), 'utf8'), 'final', 'tgs_active_queue')).toBe('Активная очередь');
    expect(nsMemberValue(fs.readFileSync(path.join(localesDir, 'en.ts'), 'utf8'), 'final', 'tgs_active_queue')).toBe('Active queue');
    expect(nsMemberValue(fs.readFileSync(path.join(localesDir, 'kk.ts'), 'utf8'), 'final', 'tgs_active_queue')).toBe('Белсенді кезек');
    expect(nsMemberValue(fs.readFileSync(path.join(localesDir, 'uz-Cyrl.ts'), 'utf8'), 'final', 'tgs_active_queue')).toBe('Фаол навбат');
    expect(nsMemberValue(fs.readFileSync(path.join(localesDir, 'uz-Latn.ts'), 'utf8'), 'final', 'tgs_active_queue')).toBe('Faol navbat');
  });
});
