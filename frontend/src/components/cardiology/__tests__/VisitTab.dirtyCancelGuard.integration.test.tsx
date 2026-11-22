import { useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import '@testing-library/jest-dom';
import { act, fireEvent, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import i18n from '@/i18n';
import { useDoctorPanelState } from '../../../hooks/useDoctorPanelState';
import { useEMRAutosave } from '../../../hooks/useEMRAutosave';
import { useEMRLeaveGuard } from '../../../hooks/useEMRLeaveGuard';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { LabDirtyGuardProvider } from '../../laboratory/LabDirtyGuardContext';
import { VisitTab } from '../VisitTab';

const emrControl = vi.hoisted(() => ({
  dirty: true,
  saveEMR: vi.fn(async (_options?: Record<string, unknown>) => ({ status: 'in_progress', row_version: 4 })),
  reloadFromServer: vi.fn(async () => undefined),
}));

vi.mock('../../emr-v2/EMRContainerV2', () => ({
  EMRContainerV2: (props: { visitId?: unknown; isReadOnly?: boolean }) => {
    const [isDirty, setIsDirty] = useState(emrControl.dirty && !props.isReadOnly);
    const saveDraft = async (options?: Record<string, unknown>) => {
      const result = await emrControl.saveEMR(options);
      if (!props.isReadOnly) flushSync(() => setIsDirty(false));
      return result;
    };
    const { suppressOnDiscard } = useEMRAutosave({
      isDirty,
      isSaving: false,
      isSigned: Boolean(props.isReadOnly),
      status: props.isReadOnly ? 'signed' : 'in_progress',
      saveEMR: saveDraft,
      debounceMs: 60_000,
      maxWaitMs: 120_000,
      enabled: !props.isReadOnly,
    });
    useEMRLeaveGuard({
      visitId: props.visitId as string | number,
      isDirty,
      isSaving: false,
      saveEMR: saveDraft,
      reloadFromServer: emrControl.reloadFromServer,
      enabled: !props.isReadOnly,
      onDiscard: suppressOnDiscard,
    });
    return <div data-testid="dirty-emr" data-visit={String(props.visitId ?? '')}>dirty synthetic EMR</div>;
  },
}));

type Visit = {
  visit_id: number;
  patient_id: number;
  status: string;
  patient_name: string;
};

function VisitCancelHarness({ status = 'in_progress' }: { status?: string }) {
  const { activeTab, handleTabChange } = useDoctorPanelState({
    defaultTab: 'visit',
    visitDeepLinkTab: 'visit',
    patientDeepLinkTab: 'patients',
  });
  const [selectedPatient, setSelectedPatient] = useState<Visit | null>({
    visit_id: 17,
    patient_id: 23,
    status,
    patient_name: 'SYNTHETIC PATIENT',
  });
  const navigationEpochRef = useRef(0);

  return (
    <>
      <output data-testid="active-tab">{activeTab}</output>
      <output data-testid="selected-visit">{selectedPatient ? String(selectedPatient.visit_id) : 'none'}</output>
      <output data-testid="navigation-epoch">{navigationEpochRef.current}</output>
      {activeTab === 'visit' && (
        <VisitTab
          selectedPatient={selectedPatient}
          onCancel={() => {
            handleTabChange('queue', () => {
              navigationEpochRef.current += 1;
              setSelectedPatient(null);
            });
          }}
          onComplete={() => undefined}
          onGoToAppointments={() => handleTabChange('patients')}
          getColor={(key) => key}
          getFontSize={(key) => key}
        />
      )}
      {activeTab === 'queue' && <div data-testid="queue">queue</div>}
    </>
  );
}

function renderVisit(status = 'in_progress') {
  return renderWithProviders(
    <LabDirtyGuardProvider>
      <VisitCancelHarness status={status} />
    </LabDirtyGuardProvider>,
    { routerProps: { initialEntries: ['/doctor/cardiology?tab=visit'] } },
  );
}

async function settle() {
  await act(async () => {
    for (let i = 0; i < 6; i += 1) await Promise.resolve();
  });
}

describe('VisitTab cancel is atomic with the cardiology leave guard', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    emrControl.dirty = true;
    emrControl.saveEMR.mockResolvedValue({ status: 'in_progress', row_version: 4 });
    await act(async () => { await i18n.changeLanguage('ru'); });
  });

  it('Stay keeps the visit mounted and does not invalidate pending work', async () => {
    renderVisit();

    fireEvent.click(await screen.findByRole('button', { name: 'Отменить' }));
    const dialog = await screen.findByRole('dialog');
    expect(screen.getByTestId('dirty-emr')).toBeInTheDocument();
    expect(screen.getByTestId('active-tab')).toHaveTextContent('visit');
    expect(screen.getByTestId('selected-visit')).toHaveTextContent('17');
    expect(screen.getByTestId('navigation-epoch')).toHaveTextContent('0');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Отмена' }));
    await settle();

    expect(screen.getByTestId('dirty-emr')).toBeInTheDocument();
    expect(screen.getByTestId('active-tab')).toHaveTextContent('visit');
    expect(screen.getByTestId('selected-visit')).toHaveTextContent('17');
    expect(screen.getByTestId('navigation-epoch')).toHaveTextContent('0');
    expect(emrControl.saveEMR).not.toHaveBeenCalled();
  });

  it('Discard suppresses the autosave before clearing the visit and switching once', async () => {
    renderVisit();

    fireEvent.click(await screen.findByRole('button', { name: 'Отменить' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Выйти без сохранения' }));

    expect(await screen.findByTestId('queue')).toBeInTheDocument();
    expect(screen.queryByTestId('dirty-emr')).not.toBeInTheDocument();
    expect(screen.getByTestId('active-tab')).toHaveTextContent('queue');
    expect(screen.getByTestId('selected-visit')).toHaveTextContent('none');
    expect(screen.getByTestId('navigation-epoch')).toHaveTextContent('1');
    await settle();
    expect(emrControl.saveEMR).not.toHaveBeenCalled();
  });

  it('a rejected save leaves the dirty visit intact and the dialog actionable', async () => {
    emrControl.saveEMR.mockRejectedValueOnce(new Error('409 version conflict'));
    renderVisit();

    fireEvent.click(await screen.findByRole('button', { name: 'Отменить' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Сохранить и перейти' }));
    await settle();

    expect(emrControl.saveEMR).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('dirty-emr')).toBeInTheDocument();
    expect(screen.getByTestId('active-tab')).toHaveTextContent('visit');
    expect(screen.getByTestId('selected-visit')).toHaveTextContent('17');
    expect(screen.getByTestId('navigation-epoch')).toHaveTextContent('0');
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('an acknowledged save commits the cancel side effects only after the save', async () => {
    renderVisit();

    fireEvent.click(await screen.findByRole('button', { name: 'Отменить' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Сохранить и перейти' }));

    expect(await screen.findByTestId('queue')).toBeInTheDocument();
    expect(emrControl.saveEMR).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('selected-visit')).toHaveTextContent('none');
    expect(screen.getByTestId('navigation-epoch')).toHaveTextContent('1');
  });

  it('a completed read-only visit returns to the queue without a dialog', async () => {
    renderVisit('served');

    fireEvent.click(await screen.findByRole('button', { name: 'Вернуться в очередь' }));

    expect(await screen.findByTestId('queue')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByTestId('selected-visit')).toHaveTextContent('none');
    expect(screen.getByTestId('navigation-epoch')).toHaveTextContent('1');
    expect(emrControl.saveEMR).not.toHaveBeenCalled();
  });
});
