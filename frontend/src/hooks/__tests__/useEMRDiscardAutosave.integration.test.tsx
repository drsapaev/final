import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';
import {
  LabDirtyGuardProvider,
  useGuardedLabNavigate,
} from '../../components/laboratory/LabDirtyGuardContext';
import { useEMRAutosave } from '../useEMRAutosave';
import { useEMRLeaveGuard } from '../useEMRLeaveGuard';

/**
 * RETRO-3971-04 post-merge P1 — exercise BOTH real hooks together.
 * A stubbed useEMRLeaveGuard alone cannot see the #4009 unmount flush.
 * All clinical identifiers and data are synthetic.
 */

function Location() {
  const { pathname } = useLocation();
  return <div data-testid="path">{pathname}</div>;
}

type SaveMock = Mock<(opts?: Record<string, unknown>) => Promise<unknown>>;
type ReloadMock = Mock<() => Promise<unknown>>;

interface Harness {
  saveEMR: SaveMock;
  reload: ReloadMock;
}

function DraftEditor({ control }: { control: Harness }) {
  const [isDirty] = React.useState(true);

  const { suppressOnDiscard } = useEMRAutosave({
    isDirty,
    isSaving: false,
    isSigned: false,
    status: 'in_progress',
    saveEMR: control.saveEMR,
    debounceMs: 60_000,
    maxWaitMs: 120_000,
    enabled: true,
  });

  useEMRLeaveGuard({
    visitId: 42,
    isDirty,
    isSaving: false,
    saveEMR: control.saveEMR,
    reloadFromServer: control.reload,
    onDiscard: suppressOnDiscard,
  });

  return <div data-testid="editor">dirty synthetic EMR</div>;
}

function DoctorRoute({ control }: { control: Harness }) {
  const [isMounted, setMounted] = React.useState(true);
  const navigate = useGuardedLabNavigate();
  return (
    <>
      {isMounted && <DraftEditor control={control} />}
      <button type="button" onClick={() => navigate('/profile')}>leave doctor</button>
      <button type="button" onClick={() => setMounted(false)}>force unmount</button>
    </>
  );
}

function HarnessApp({ control }: { control: Harness }) {
  return (
    <ThemeProvider>
      <MemoryRouter initialEntries={['/doctor/dermatology']}>
        <LabDirtyGuardProvider>
          <Location />
          <Routes>
            <Route path="/doctor/dermatology" element={<DoctorRoute control={control} />} />
            <Route path="/profile" element={<div>profile page</div>} />
          </Routes>
        </LabDirtyGuardProvider>
      </MemoryRouter>
    </ThemeProvider>
  );
}

async function flush() {
  await act(async () => {
    for (let i = 0; i < 8; i += 1) await Promise.resolve();
  });
}

function makeHarness(): Harness {
  return {
    saveEMR: vi.fn<(opts?: Record<string, unknown>) => Promise<unknown>>(
      async () => ({ status: 'in_progress', row_version: 5 }),
    ),
    // Intentionally never resolves: waiting on a GET cannot be the mechanism
    // protecting a discarded draft from an unmount autosave.
    reload: vi.fn<() => Promise<unknown>>(
      () => new Promise<unknown>(() => undefined),
    ),
  };
}

describe('EMR Discard × unmount autosave integrity (RETRO-3971-04)', () => {
  beforeEach(async () => {
    await act(async () => { await i18n.changeLanguage('ru'); });
  });

  it('explicit Discard never saves dirty data, even if the baseline GET hangs', async () => {
    const control = makeHarness();
    render(<HarnessApp control={control} />);
    await flush();

    fireEvent.click(screen.getByRole('button', { name: 'leave doctor' }));
    const dialog = await screen.findByRole('dialog');
    expect(screen.getByTestId('editor')).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Выйти без сохранения' }));
    await flush();

    expect(screen.getByTestId('path')).toHaveTextContent('/profile');
    expect(screen.queryByTestId('editor')).not.toBeInTheDocument();
    expect(control.reload).toHaveBeenCalledTimes(1);
    expect(control.saveEMR).not.toHaveBeenCalled();
  });

  it('uncontrolled unmount without Discard preserves the #4009 final flush', async () => {
    const control = makeHarness();
    render(<HarnessApp control={control} />);
    await flush();

    fireEvent.click(screen.getByRole('button', { name: 'force unmount' }));
    await flush();

    expect(screen.queryByTestId('editor')).not.toBeInTheDocument();
    expect(control.saveEMR).toHaveBeenCalledTimes(1);
    expect(control.saveEMR).toHaveBeenCalledWith({ isDraft: true });
  });

  it('Stay does not suppress the later uncontrolled unmount flush', async () => {
    const control = makeHarness();
    render(<HarnessApp control={control} />);
    await flush();

    fireEvent.click(screen.getByRole('button', { name: 'leave doctor' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Отмена' }));
    await flush();
    expect(screen.getByTestId('editor')).toBeInTheDocument();
    expect(control.saveEMR).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'force unmount' }));
    await flush();
    expect(control.saveEMR).toHaveBeenCalledTimes(1);
  });
});
