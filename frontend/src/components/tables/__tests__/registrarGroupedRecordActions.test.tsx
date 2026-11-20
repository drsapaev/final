import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../../contexts/ThemeContext';
import { useRegistrarActions } from '../../../pages/registrar/useRegistrarActions';
import { useRegistrarDialogs } from '../../../pages/registrar/useRegistrarDialogs';
import { useRegistrarReschedule } from '../../../pages/registrar/useRegistrarReschedule';
import { useRegistrarRowActions } from '../../../pages/registrar/useRegistrarRowActions';
import { adaptQueueEntry } from '../../../pages/registrar/registrarQueueAdapter';
import RegistrarDialogsLayer from '../../../pages/registrar/views/RegistrarDialogsLayer';
import { aggregatePatientsForAllDepartments } from '../../../utils/registrarAggregation';
import EnhancedAppointmentsTable from '../EnhancedAppointmentsTable';
import type { AppointmentRow } from '../appointmentsTableContracts';

const { post, translate } = vi.hoisted(() => ({
  post: vi.fn(),
  translate: (key: string, options?: Record<string, unknown>) =>
    options?.id ? `${key} ${String(options.id)}` : key,
}));

vi.mock('../../../api/client', () => ({ api: { post }, default: { get: vi.fn(), put: vi.fn() } }));
vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: translate, language: 'ru' }),
}));
vi.mock('../../../services/notify', () => ({ default: { error: vi.fn(), success: vi.fn() } }));
vi.mock('../../dialogs/PaymentDialog', () => ({ default: () => null }));
vi.mock('../../dialogs/PrintDialog', () => ({ default: () => null }));
vi.mock('../../payment/PaymentManager', () => ({ default: () => null }));
vi.mock('../../wizard/AppointmentWizardV2', () => ({ default: () => null }));
vi.mock('../../registrar/ForceMajeureModal', () => ({ default: () => null }));

const noop = () => undefined;
const themeValue = () => '';
const confirm = async () => true;
const visitDay = '2099-11-20';
const cancelLabel = 'misc.eat_cancel_aria';
const rescheduleLabel = 'misc.eat_reschedule_aria';
const reason = 'Synthetic cancellation';

function record(id: number, visitId: number, status: string, allowed = true) {
  const row = adaptQueueEntry({
    id,
    canonical_record_id: id,
    record_kind: 'online_queue',
    visit_id: visitId,
    patient_id: 777,
    patient_name: 'Synthetic patient',
    record_date: visitDay,
    status,
    doctor_name: `Synthetic clinician ${visitId}`,
    services: [{ name: `Synthetic service ${visitId}` }],
    available_actions: allowed ? ['cancel', 'reschedule'] : [],
    can_cancel: allowed,
    can_reschedule: allowed,
  }, { specialty: 'cardiology' }, { date: visitDay }, visitDay, 'Unknown patient');
  if (!row) throw new Error('Invalid synthetic worklist record');
  return row;
}

function Worklist({ rows }: { rows: Record<string, unknown>[] }) {
  const appointments = aggregatePatientsForAllDepartments(rows);
  const dialogs = useRegistrarDialogs();
  const reschedule = useRegistrarReschedule({ setAppointments: noop });
  const actions = useRegistrarActions({ appointments, loadAppointments: noop });
  const rowActions = useRegistrarRowActions({
    ...dialogs,
    ...actions,
    confirm,
    setShowWizard: noop,
    setWizardEditMode: noop,
    setWizardInitialData: noop,
    tI18n: translate,
  });
  return (
    <>
      <EnhancedAppointmentsTable data={appointments as AppointmentRow[]} onActionClick={rowActions.handleTableAction} />
      <RegistrarDialogsLayer
        {...dialogs}
        {...rowActions}
        {...actions}
        {...reschedule}
        showSlotsModal={dialogs.rescheduleDialog.open}
        rescheduleData={dialogs.rescheduleDialog.data}
        showWizard={false}
        wizardEditMode={false}
        wizardInitialData={null}
        isProcessing={false}
        activeTab={null}
        getColor={themeValue}
        getSpacing={themeValue}
        getFontSize={themeValue}
        setShowWizard={noop}
        setWizardEditMode={noop}
        setWizardInitialData={noop}
        setIsProcessing={noop}
        loadAppointments={noop}
        loadIntegratedData={noop}
        handleWizardComplete={noop}
        confirm={confirm}
        tI18n={translate}
      />
    </>
  );
}

const renderWorklist = (rows: Record<string, unknown>[]) => render(<Worklist rows={rows} />, { wrapper: ThemeProvider });
const action = (name: string) => screen.getByRole('button', { name });
const fillReason = () => fireEvent.change(screen.getByLabelText('misc.cd_prichina_otmeny_zapisi'), {
  target: { value: reason },
});
const rescheduleTomorrow = () => fireEvent.click(screen.getByRole('button', { name: /registrarPanel\.tomorrow/ }));

describe('Registrar grouped record actions (REGAGG-FE-002)', () => {
  beforeEach(() => {
    post.mockReset().mockResolvedValue({ data: { success: true, success_count: 1, failed_count: 0 } });
  });
  afterEach(cleanup);

  it.each([['pending', 'confirmed'], ['confirmed', 'pending']])(
    'shows the mixed badge and addresses the selected record only (%s + %s)',
    async (first, second) => {
      renderWorklist([record(901, 101, first), record(902, 102, second)]);
      expect(screen.getByText('misc.eat_status_mixed')).toBeInTheDocument();

      fireEvent.click(action(cancelLabel));
      fillReason();
      const submit = action('misc.cd_podtverdit_otmenu');
      expect(submit).toBeDisabled();
      fireEvent.change(screen.getByLabelText('registrar.cancel_select_record'), {
        target: { value: 'online_queue:902' },
      });
      fireEvent.click(submit);
      await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
      expect(post).toHaveBeenLastCalledWith('/registrar/records/actions', {
        action: 'cancel', reason, records: [{ record_kind: 'online_queue', record_id: 902 }],
      });
      await waitFor(() => expect(screen.queryByLabelText('registrar.cancel_select_record')).toBeNull());

      fireEvent.click(action(rescheduleLabel));
      rescheduleTomorrow();
      await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
      fireEvent.change(screen.getByLabelText('registrar.reschedule_select_visit_label'), {
        target: { value: '102' },
      });
      rescheduleTomorrow();
      await waitFor(() => expect(post).toHaveBeenCalledTimes(2));
      expect(post).toHaveBeenLastCalledWith('/visits/visits/102/reschedule/tomorrow');
    },
  );

  it('shows and submits the waiting record alone when its neighbor is done', async () => {
    renderWorklist([record(901, 101, 'done', false), record(902, 102, 'waiting')]);
    fireEvent.click(action(cancelLabel));
    expect(screen.queryByLabelText('registrar.cancel_select_record')).toBeNull();
    expect(screen.getByText(/#902/)).toBeInTheDocument();
    fillReason();
    fireEvent.click(action('misc.cd_podtverdit_otmenu'));
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post).toHaveBeenLastCalledWith('/registrar/records/actions', {
      action: 'cancel', reason, records: [{ record_kind: 'online_queue', record_id: 902 }],
    });
    await waitFor(() => expect(screen.queryByLabelText('misc.cd_prichina_otmeny_zapisi')).toBeNull());

    fireEvent.click(action(rescheduleLabel));
    expect(screen.queryByLabelText('registrar.reschedule_select_visit_label')).toBeNull();
    expect(screen.getByText(/registrar\.reschedule_visit_option 102/)).toBeInTheDocument();
    rescheduleTomorrow();
    await waitFor(() => expect(post).toHaveBeenCalledTimes(2));
    expect(post).toHaveBeenLastCalledWith('/visits/visits/102/reschedule/tomorrow');
  });

  it('hides both actions when the backend denies them', () => {
    renderWorklist([record(901, 101, 'pending', false), record(902, 102, 'confirmed', false)]);
    expect(screen.queryByRole('button', { name: cancelLabel })).toBeNull();
    expect(screen.queryByRole('button', { name: rescheduleLabel })).toBeNull();
    expect(post).not.toHaveBeenCalled();
  });

  it('keeps the controls available for a uniform eligible group', () => {
    renderWorklist([record(901, 101, 'confirmed'), record(902, 102, 'confirmed')]);
    expect(screen.queryByText('misc.eat_status_mixed')).toBeNull();
    expect(action(cancelLabel)).toBeInTheDocument();
    expect(action(rescheduleLabel)).toBeInTheDocument();
  });
});
