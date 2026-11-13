import React, { useRef } from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';
import {
  LabDirtyGuardProvider,
  useGuardedLabNavigate,
  useLabDirtyGuard,
} from '../../components/laboratory/LabDirtyGuardContext';
import { useCardiologistHotkeys } from '../useCardiologistHotkeys';
import { useDoctorPanelState } from '../useDoctorPanelState';

/**
 * RETRO-3971-04 post-merge P1 (third navigation gap): same-route tab
 * switching — sidebar clicks AND Ctrl+1..5 hotkeys (useCardiologistHotkeys →
 * useDoctorPanelState.handleTabChange) — unmounts a dirty cardiology EMR
 * without ANY leave decision. The route pathname never changes, so the
 * browser-Back sentinel has no chance to intervene either.
 *
 * Acceptance (PR #4000 ledger, P1 comment): a dirty EMR tab switch must
 * present the shared Stay/Save/Discard dialog; a rejected save keeps the
 * visit and the unsaved text; an acknowledged save performs the switch once;
 * a clean EMR keeps the cheap instant navigation; dermatology is parallel.
 * History isolation / start-at-non-guarded-page pattern mirrors
 * LabGuardedNavigator.emrRoutes.test.tsx. All clinical data is synthetic.
 */

const CARDIOLOGY_PANEL_CONFIG = {
  defaultTab: 'queue',
  visitDeepLinkTab: 'visit',
  patientDeepLinkTab: 'patients',
} as const;

const DERMATOLOGY_PANEL_CONFIG = {
  defaultTab: 'queue',
  visitDeepLinkTab: 'visit',
  patientDeepLinkTab: 'patients',
  validTabs: ['queue', 'visit', 'patients'],
} as const;

interface DraftControl {
  dirty: { current: boolean };
  save: ReturnType<typeof vi.fn>;
  discard: ReturnType<typeof vi.fn>;
  cancelVisit: () => void;
}

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname + location.search}</div>;
}

function DraftVisitEditor({ control }: { control: DraftControl }) {
  const dirtyRef = useRef(control.dirty.current);
  dirtyRef.current = control.dirty.current;
  // Тот же паттерн, что useEMRLeaveGuard: deps — СТАБИЛЬНЫЙ
  // registerDirtySource (useCallback в провайдере), не весь объект guard —
  // иначе каждый флип historyGuardEngaged пере-регистрировал бы источник
  // и осциллировал arm/collapse.
  const registerDirtySource = useLabDirtyGuard().registerDirtySource;
  React.useEffect(() => registerDirtySource({
    id: 'emr-visit-77',
    isDirty: () => dirtyRef.current,
    save: control.save as unknown as () => Promise<void>,
    discard: control.discard as unknown as () => void,
    // eslint-disable-next-line react-hooks/exhaustive-deps -- control стабилен внутри одного теста (создан до mount)
  }), [registerDirtySource]);
  return <div data-testid="editor">synthetic visit EMR (unsaved clinical text)</div>;
}

function PanelHarness({
  control,
  panel,
}: {
  control: DraftControl;
  panel: 'cardiology' | 'dermatology';
}) {
  const config = panel === 'cardiology'
    ? CARDIOLOGY_PANEL_CONFIG
    : DERMATOLOGY_PANEL_CONFIG;
  const { activeTab, handleTabChange: goToTab } = useDoctorPanelState(config);
  useCardiologistHotkeys({ setActiveTab: (tab: string) => goToTab(tab) });
  return (
    <div>
      {activeTab === 'visit'
        ? <DraftVisitEditor control={control} />
        : <div data-testid="other-tab">{activeTab} view</div>}
      <button type="button" onClick={() => goToTab('queue')}>tab-queue</button>
      <button type="button" onClick={() => goToTab('patients')}>tab-patients</button>
      <button type="button" onClick={() => goToTab('visit')}>tab-visit</button>
      <button type="button" onClick={() => goToTab('queue', control.cancelVisit)}>cancel-visit</button>
    </div>
  );
}

function ProfileShell({ panel }: { panel: 'cardiology' | 'dermatology' }) {
  const navigate = useGuardedLabNavigate();
  return (
    <div>
      profile shell
      <button
        type="button"
        onClick={() => navigate(panel === 'cardiology'
          ? '/doctor/cardiology?tab=visit'
          : '/doctor/dermatology?tab=visit')}
      >
        open-panel
      </button>
    </div>
  );
}

function HarnessApp({ control, panel }: { control: DraftControl; panel: 'cardiology' | 'dermatology' }) {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <LabDirtyGuardProvider>
          <LocationProbe />
          <Routes>
            <Route path="/profile" element={<ProfileShell panel={panel} />} />
            <Route path="/doctor/cardiology" element={<PanelHarness control={control} panel="cardiology" />} />
            <Route path="/doctor/dermatology" element={<PanelHarness control={control} panel="dermatology" />} />
          </Routes>
        </LabDirtyGuardProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}

async function settleRouter(expectedUrl?: string) {
  await act(async () => {
    for (let i = 0; i < 6; i += 1) await Promise.resolve();
    const deadline = Date.now() + 1500;
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 25));
      const current = window.location.pathname + window.location.search;
      if (!expectedUrl || current === expectedUrl) break;
    }
  });
}

async function openDirtyPanel(panel: 'cardiology' | 'dermatology' = 'cardiology', dirty = true) {
  const control: DraftControl = {
    dirty: { current: dirty },
    save: vi.fn(async () => ({ status: 'in_progress', row_version: 3 })),
    discard: vi.fn(),
    cancelVisit: vi.fn(),
  };
  const panelUrl = panel === 'cardiology'
    ? '/doctor/cardiology?tab=visit'
    : '/doctor/dermatology?tab=visit';
  render(<HarnessApp control={control} panel={panel} />);
  await settleRouter('/profile');

  fireEvent.click(screen.getByRole('button', { name: 'open-panel' }));
  await settleRouter(panelUrl);

  expect(screen.getByTestId('location')).toHaveTextContent(panelUrl);
  if (dirty) {
    expect(screen.getByTestId('editor')).toBeInTheDocument();
  }
  return { control, panelUrl };
}

function pressHotkey(key: string) {
  // useCardiologistHotkeys слушает document keydown (ignore input targets —
  // fireEvent на document не попадает в INPUT/TEXTAREA).
  fireEvent.keyDown(document, { key, ctrlKey: true });
}

describe('Same-route doctor tab switching through the shared leave guard (RETRO-3971-04 P1)', () => {
  it('the visit cancel side effect waits for the shared leave decision', async () => {
    const { control } = await openDirtyPanel();

    fireEvent.click(screen.getByRole('button', { name: 'cancel-visit' }));
    const dialog = await screen.findByRole('dialog');

    expect(screen.getByTestId('editor')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/cardiology?tab=visit');
    expect(control.cancelVisit).not.toHaveBeenCalled();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Отмена' }));
    await settleRouter('/doctor/cardiology?tab=visit');
    expect(control.cancelVisit).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'cancel-visit' }));
    const discardDialog = await screen.findByRole('dialog');
    fireEvent.click(within(discardDialog).getByRole('button', { name: 'Выйти без сохранения' }));
    await settleRouter('/doctor/cardiology?tab=queue');

    expect(control.cancelVisit).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId('editor')).not.toBeInTheDocument();
    expect(screen.getByTestId('other-tab')).toHaveTextContent('queue view');
  });

  beforeEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
    // Изоляция истории: возврат к самой ранней записи (jsdom-подобный go в
    // этом окружении no-op — stderr-предупреждение не фатально), затем
    // replace на НЕ-guarded /profile: layout-эффект провайдера снимает
    // устаревший sentinel предыдущего теста БЕЗ collapse-back.
    window.history.go(-window.history.length + 1);
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 25));
    });
    window.history.replaceState(null, '', '/profile');
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 25));
    });
  });

  it('Ctrl+1 on a dirty cardiology visit EMR opens the guard dialog and keeps the editor mounted', async () => {
    const { control } = await openDirtyPanel();

    pressHotkey('1');
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 120));
    });

    expect(screen.getByTestId('editor')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/cardiology?tab=visit');
    const dialog = screen.queryByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(control.save).not.toHaveBeenCalled();
    expect(control.discard).not.toHaveBeenCalled();
  });

  it('Discard on the tab-switch dialog switches the tab and unmounts the editor', async () => {
    const { control } = await openDirtyPanel();

    pressHotkey('1');
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Выйти без сохранения' }));
    await settleRouter('/doctor/cardiology?tab=queue');

    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/cardiology?tab=queue');
    expect(screen.queryByTestId('editor')).not.toBeInTheDocument();
    expect(screen.getByTestId('other-tab')).toHaveTextContent('queue view');
    expect(control.discard).toHaveBeenCalledTimes(1);
  });

  it('a rejected save keeps the dirty editor mounted and the dialog actionable', async () => {
    const { control } = await openDirtyPanel();
    control.save.mockRejectedValueOnce(new Error('409 version conflict'));

    pressHotkey('1');
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Сохранить и перейти' }));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 120));
    });

    expect(control.save).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('editor')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/cardiology?tab=visit');
    expect(screen.queryByRole('dialog')).toBeInTheDocument();
  });

  it('an acknowledged save performs the tab switch exactly once', async () => {
    const { control } = await openDirtyPanel();

    pressHotkey('1');
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Сохранить и перейти' }));
    await settleRouter('/doctor/cardiology?tab=queue');

    expect(control.save).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/cardiology?tab=queue');
    expect(screen.queryByTestId('editor')).not.toBeInTheDocument();
  });

  it('Stay (Отмена) keeps the dirty editor on the visit tab', async () => {
    const { control } = await openDirtyPanel();

    pressHotkey('1');
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Отмена' }));
    await settleRouter('/doctor/cardiology?tab=visit');

    expect(screen.getByTestId('editor')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/cardiology?tab=visit');
    expect(control.save).not.toHaveBeenCalled();
    expect(control.discard).not.toHaveBeenCalled();
  });

  it('a clean EMR keeps the cheap instant tab navigation (no dialog)', async () => {
    await openDirtyPanel('cardiology', false);

    pressHotkey('1');
    await settleRouter('/doctor/cardiology?tab=queue');

    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/cardiology?tab=queue');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('switching to the SAME tab never opens a dialog and never unmounts the editor', async () => {
    const { control } = await openDirtyPanel();

    pressHotkey('2'); // Ctrl+2 → visit — the tab the user is already on
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 120));
    });

    expect(screen.getByTestId('editor')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/cardiology?tab=visit');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(control.save).not.toHaveBeenCalled();
    expect(control.discard).not.toHaveBeenCalled();
  });

  it('dermatology tab switching is guarded in parallel', async () => {
    const { control } = await openDirtyPanel('dermatology');

    fireEvent.click(screen.getByRole('button', { name: 'tab-patients' }));
    const dialog = await screen.findByRole('dialog');
    expect(screen.getByTestId('editor')).toBeInTheDocument();
    expect(control.discard).not.toHaveBeenCalled();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Выйти без сохранения' }));
    await settleRouter('/doctor/dermatology?tab=patients');
    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/dermatology?tab=patients');
    expect(screen.queryByTestId('editor')).not.toBeInTheDocument();
    expect(control.discard).toHaveBeenCalledTimes(1);
  });

  it('browser Back after a clean tab switch still navigates between tabs (sentinel-compatible)', async () => {
    const { panelUrl } = await openDirtyPanel('cardiology', false);

    pressHotkey('1');
    await settleRouter('/doctor/cardiology?tab=queue');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    window.history.back();
    await settleRouter(panelUrl);

    expect(screen.getByTestId('location')).toHaveTextContent('/doctor/cardiology?tab=visit');
    expect(screen.getByTestId('editor')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
