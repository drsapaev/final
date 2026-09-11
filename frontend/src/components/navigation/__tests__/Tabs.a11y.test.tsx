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
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../api/client', () => ({
  api: {
    get: vi.fn().mockRejectedValue(new Error('offline — fallback tabs expected')),
  },
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

import Tabs, { tabButtonIdFor } from '../Tabs';

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

    // RQ-19: department controls are now ARIA tabs (role=tab inside the
    // tablist) — the status-description contract below is unchanged.
    const cardiology = await screen.findByRole('tab', { name: 'misc.mt_kardiolog' });

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
    const ecg = screen.getByRole('tab', { name: 'misc.mt_ekg' });
    expect(ecg).toHaveAccessibleDescription('final.tgs_active_queue');
  });

  // Codex P2 round 6 (thread 3945096766): the tab key is backend-defined
  // and may contain whitespace ("general medicine") — aria-describedby is
  // an IDREF list, so the generated id must be whitespace-free and must
  // still resolve in-button. The whitespace key arrives through the API
  // path (mockResolvedValueOnce overrides the rejection default), since
  // the offline fallback set only contains clean keys.
  it('department key with whitespace: describedby id stays a valid single IDREF', async () => {
    const { api } = await import('../../../api/client');
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        source: 'database',
        profiles: [
          { key: 'general medicine', title_ru: 'Общая медицина', icon: 'Heart', color: '#cc0000', queue_tags: [] },
        ],
      },
    });

    render(
      <Tabs
        departmentStats={{
          'general medicine': { todayCount: 2, hasActiveQueue: false, hasPendingPayments: false },
        }}
      />
    );

    const button = await screen.findByRole('tab', { name: 'Общая медицина' });

    const describedBy = button.getAttribute('aria-describedby');
    expect(describedBy).toBeTruthy();
    expect(describedBy).not.toMatch(/\s/);

    const target = document.getElementById(describedBy as string);
    expect(target).not.toBeNull();
    expect(button.contains(target as Node)).toBe(true);
    expect(button).toHaveAccessibleDescription('registrarPanel.today: 2');
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

    // Localized (round-6): pending_payments / today no longer Russian in
    // kk and uz-Cyrl (registrar users hear one language per locale).
    const kk = fs.readFileSync(path.join(localesDir, 'kk.ts'), 'utf8');
    const uzc = fs.readFileSync(path.join(localesDir, 'uz-Cyrl.ts'), 'utf8');
    expect(nsMemberValue(kk, 'registrarPanel', 'pending_payments')).toBe('Төлемдер күтуде');
    expect(nsMemberValue(kk, 'registrarPanel', 'today')).toBe('Бүгін');
    expect(nsMemberValue(uzc, 'registrarPanel', 'pending_payments')).toBe('Тўловни кутмоқда');
    expect(nsMemberValue(uzc, 'registrarPanel', 'today')).toBe('Бугун');
  });
});

/**
 * RQ-19 — ARIA tabs pattern for the registrar department tabs.
 *
 * Before RQ-19 the department controls were plain buttons: the tab strip
 * exposed no tablist/tab semantics, no aria-selected, no aria-controls,
 * and the WorklistView tabpanel pointed at `${activeTab}-tab` — an id NO
 * button carried (dangling IDREF, panel unlabelled for screen readers).
 * The plan contract (plan §RQ-19 / S-16): "корректны role, id,
 * aria-selected, aria-controls и клавиатура".
 *
 * Activation model — MANUAL (APG manual-activation tabs): switching the
 * active tab refetches the registrar worklist (per-tab data load), so
 * arrow keys move focus WITHOUT activating; Enter/Space or click selects.
 */
describe('RQ-19 — ARIA tabs pattern (tablist/tab, id, aria-selected, aria-controls, keyboard)', () => {
  it('department tabs are owned by a tablist and publish id/aria-selected/aria-controls', async () => {
    render(<Tabs activeTab="ecg" />);

    await waitFor(() => {
      expect(document.querySelectorAll('.tab-button.department').length).toBe(6);
    });

    const tablist = document.querySelector('.department-tabs');
    expect(tablist).toHaveAttribute('role', 'tablist');

    const tabs = within(tablist as HTMLElement).getAllByRole('tab');
    expect(tabs).toHaveLength(6);

    for (const tab of tabs) {
      const key = tab.getAttribute('data-tab') as string;
      // Shared id contract with the WorklistView tabpanel (aria-labelledby).
      expect(tab.id).toBe(tabButtonIdFor(key));
      // Backend keys may be whitespace-bearing — ids must not be.
      expect(tab.id).not.toMatch(/\s/);
      // The controlled panel is the registrar worklist region.
      expect(tab).toHaveAttribute('aria-controls', 'main-content');
      expect(tab).toHaveAttribute('aria-selected');
    }

    // Selected state is exposed non-visually (not via color/icon only).
    expect(screen.getByRole('tab', { name: 'misc.mt_ekg' })).toHaveAttribute('aria-selected', 'true');
    for (const tab of tabs) {
      if (tab.getAttribute('data-tab') !== 'ecg') {
        expect(tab).toHaveAttribute('aria-selected', 'false');
      }
    }
  });

  it('decorative animated indicator stays out of the tablist owned elements', async () => {
    render(<Tabs />);

    await waitFor(() => {
      expect(document.querySelectorAll('.tab-button.department').length).toBe(6);
    });

    const indicator = document.querySelector('.department-tabs .tab-indicator');
    expect(indicator).not.toBeNull();
    expect(indicator).toHaveAttribute('aria-hidden', 'true');
  });

  it('roving tabindex: selected tab keeps 0, siblings -1; without selection all stay tabbable', async () => {
    const withSelection = render(<Tabs activeTab="ecg" />);
    await waitFor(() => {
      expect(document.querySelectorAll('.tab-button.department').length).toBe(6);
    });
    for (const tab of Array.from(document.querySelectorAll<HTMLButtonElement>('[role="tab"]'))) {
      expect(tab.getAttribute('tabindex')).toBe(tab.getAttribute('data-tab') === 'ecg' ? '0' : '-1');
    }
    withSelection.unmount();

    // All-departments view: no tab is selected — every tab remains in the
    // Tab sequence, preserving today's keyboard order in the default view.
    render(<Tabs activeTab={null} />);
    await waitFor(() => {
      expect(document.querySelectorAll('.tab-button.department').length).toBe(6);
    });
    for (const tab of Array.from(document.querySelectorAll<HTMLButtonElement>('[role="tab"]'))) {
      expect(tab.getAttribute('tabindex')).toBe('0');
    }
  });

  it('manual-activation keyboard: Arrow/Home/End move focus only, selection untouched', async () => {
    const onTabChange = vi.fn();
    render(<Tabs activeTab="ecg" onTabChange={onTabChange} />);

    await waitFor(() => {
      expect(document.querySelectorAll('.tab-button.department').length).toBe(6);
    });

    const tabs = Array.from(document.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
    expect(tabs.map((tab) => tab.getAttribute('data-tab'))).toEqual([
      'cardiology', 'ecg', 'dermatology', 'stomatology', 'lab', 'procedures',
    ]);

    tabs[1]!.focus(); // ecg — the selected tab (tabindex 0)
    expect(document.activeElement).toBe(tabs[1]);

    fireEvent.keyDown(tabs[1]!, { key: 'ArrowRight' });
    expect(document.activeElement).toBe(tabs[2]);
    fireEvent.keyDown(tabs[2]!, { key: 'ArrowLeft' });
    expect(document.activeElement).toBe(tabs[1]);
    fireEvent.keyDown(tabs[1]!, { key: 'End' });
    expect(document.activeElement).toBe(tabs[5]);
    fireEvent.keyDown(tabs[5]!, { key: 'ArrowRight' }); // wraps to first
    expect(document.activeElement).toBe(tabs[0]);
    fireEvent.keyDown(tabs[0]!, { key: 'Home' });
    expect(document.activeElement).toBe(tabs[0]);
    fireEvent.keyDown(tabs[0]!, { key: 'ArrowLeft' }); // wraps to last
    expect(document.activeElement).toBe(tabs[5]);

    // Manual activation: arrows NEVER select — selection happens via
    // Enter/Space (native click) because switching tabs triggers the
    // worklist data fetch.
    expect(onTabChange).not.toHaveBeenCalled();
  });

  it('S-16 scale: 1/10/20 whitespace-keyed tabs keep the contract and long labels in the name', async () => {
    const { api } = await import('../../../api/client');

    for (const count of [1, 10, 20]) {
      const profiles = Array.from({ length: count }, (_, i) => ({
        key: `dept ${i}`, // whitespace keys exercise the id encoding
        title_ru: `Синтетическое отделение с очень длинным названием профиля очереди ${i + 1}`,
        icon: 'Heart',
        color: '#cc0000',
        queue_tags: [],
      }));
      vi.mocked(api.get).mockResolvedValueOnce({
        data: { source: 'database', profiles },
      });

      const activeKey = count === 1 ? 'dept 0' : 'dept 3';
      const { unmount } = render(<Tabs activeTab={activeKey} />);
      await waitFor(() => {
        expect(document.querySelectorAll('.tab-button.department').length).toBe(count);
      });

      const tabs = within(document.querySelector('.department-tabs') as HTMLElement).getAllByRole('tab');
      expect(tabs).toHaveLength(count);

      // Exactly one selected tab, distinguishable without color/icon.
      const selected = tabs.filter((tab) => tab.getAttribute('aria-selected') === 'true');
      expect(selected).toHaveLength(1);
      expect(selected[0]).toHaveAttribute('data-tab', activeKey);
      // Long label survives into the accessible name (aria-label).
      expect(selected[0]).toHaveAttribute(
        'aria-label',
        `Синтетическое отделение с очень длинным названием профиля очереди ${activeKey === 'dept 0' ? 1 : 4}`,
      );

      for (const tab of tabs) {
        expect(tab.id).toBe(tabButtonIdFor(tab.getAttribute('data-tab') as string));
        expect(tab.id).not.toMatch(/\s/);
        expect(tab).toHaveAttribute('aria-controls', 'main-content');
      }
      unmount();
    }
  });
});
