/**
 * DERMAURL-FE-001 / DERMAURL-FE-002 (audit 3892, post-merge group 7
 * «dermatology deep links») — fail-first regressions for the URL
 * patient/visit resolution in DermatologistPanelUnified:
 *
 * - DERMAURL-FE-001: a deep link with a CONTRADICTORY patientId + visitId
 *   pair must not produce an unverified patient/visit context in the EMR
 *   editor. When both IDs are supplied, the matched queue row must
 *   satisfy both; an unmatched pair must fail closed (no synthetic
 *   patient with a fabricated visit), never open the editor at the
 *   URL-supplied visit.
 * - DERMAURL-FE-002: a manual patient selection made after a deep link
 *   was applied must survive — the URL resolution must not clobber it
 *   back to the stale deep-link target on every state change.
 *
 * Red-first: on the pre-fix source the mixed-pair and fallback cases fail
 * (the editor renders a fabricated context), and the manual-selection
 * case fails (the URL row is re-applied over the clinician's choice). The
 * consistent-pair control passes on both.
 */
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useNavigate } from 'react-router-dom';
import { renderWithProviders } from '../../test/renderWithProviders';

const holder = vi.hoisted(() => ({
  manualPatient: null as Record<string, unknown> | null,
  navigate: null as ((to: string) => void) | null,
}));

function NavigateProbe() {
  const navigate = useNavigate();
  holder.navigate = navigate as unknown as (to: string) => void;
  return null;
}

vi.mock('../../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));
vi.mock('../../api/runtime', () => ({
  getApiBaseUrl: () => 'http://synthetic.test/api/v1',
  getApiOrigin: () => 'http://synthetic.test',
}));
vi.mock('../../utils/tokenManager', () => ({
  default: { getAccessToken: vi.fn() },
}));
vi.mock('../../utils/canonicalVisit', () => ({
  resolveCanonicalVisitId: async (row: { visit_id?: unknown }) =>
    (row?.visit_id ?? null) as string | number | null,
}));
vi.mock('../../utils/logger', () => ({
  default: { warn: vi.fn(), info: vi.fn(), error: vi.fn() },
}));
vi.mock('../../services/notify', () => ({
  default: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));
vi.mock('../../services/queue', () => ({
  queueService: { completeVisit: vi.fn(), callNextWaiting: vi.fn(), startVisit: vi.fn() },
}));
vi.mock('../../services/print', () => ({
  printService: { printPrescription: vi.fn() },
}));
vi.mock('../../services/panelPrint', () => ({
  printPanelTicket: vi.fn(),
}));
vi.mock('../../stores/auth', () => ({
  subscribe: () => () => undefined,
}));
vi.mock('../../components/emr-v2/EMRContainerV2', () => ({
  EMRContainerV2: (props: { visitId?: unknown; patientId?: unknown; onDirtyChange?: unknown }) => (
    <div
      data-testid="emr-editor"
      data-visit={String(props.visitId ?? '')}
      data-patient={String(props.patientId ?? '')}
      data-dirty-callback={typeof props.onDirtyChange === 'function' ? 'yes' : 'no'}
    />
  ),
}));
vi.mock('../../components/dermatology/DermaVisitGallery', () => ({
  default: () => <div data-testid="derma-gallery" />,
}));
vi.mock('../../components/QueueIntegration', () => ({
  default: () => <div data-testid="queue-integration" />,
}));
vi.mock('../../components/tables/EnhancedAppointmentsTable', () => ({
  default: () => <div data-testid="appointments-table" />,
}));
vi.mock('../../components/dermatology/DermaPatientsTab', () => ({
  // Exposes the real manual selection path: onSelectPatient.
  default: (props: { onSelectPatient?: (patient: Record<string, unknown>) => void }) => (
    <button
      type="button"
      data-testid="patients-tab"
      aria-label="Select the synthetic patient"
      onClick={() => props.onSelectPatient?.(holder.manualPatient as Record<string, unknown>)}
    />
  ),
}));
vi.mock('../../components/ai/AIAssistant', () => ({ default: () => <div /> }));
vi.mock('../../components/VisitTimeline', () => ({ default: () => <div /> }));
vi.mock('../../components/doctor/AppointmentSummaryBar', () => ({ default: () => <div /> }));
vi.mock('../../components/common/EditPatientModal', () => ({ default: () => <div /> }));
vi.mock('../../components/common/ScheduleNextModal', () => ({
  default: () => <div data-testid="schedule-next-modal" />,
}));
vi.mock('../../components/common/SessionWarningModal', () => ({ default: () => <div /> }));
vi.mock('../../components/common/ConfirmDialog', () => ({
  useConfirm: () => [() => Promise.resolve(true), null],
}));
vi.mock('../../hooks/useSessionTimeoutWarning', () => ({
  useSessionTimeoutWarning: () => undefined,
}));
vi.mock('../../hooks/useDermaHotkeys', () => ({ useDermaHotkeys: vi.fn() }));
vi.mock('../../hooks/useVisitLifecycle', () => ({ useVisitLifecycle: vi.fn() }));
vi.mock('../../useDermatologyPatientHistory', () => ({
  useDermatologyPatientHistory: () => ({
    appointments: [],
    skinExaminations: [],
    cosmeticProcedures: [],
    skinExaminationsTotal: 0,
    cosmeticProceduresTotal: 0,
    hasMoreExaminations: false,
    hasMoreProcedures: false,
    loadingMoreExaminations: false,
    loadingMoreProcedures: false,
    loadMoreExaminations: () => undefined,
    loadMoreProcedures: () => undefined,
    loading: false,
    ready: true,
    error: null,
  }),
}));

import { api } from '../../api/client';
import tokenManager from '../../utils/tokenManager';
import DermatologistPanelUnified from '../DermatologistPanelUnified';

const mockedGet = vi.mocked(api.get);

function queueResponse(rows: Array<Record<string, unknown>>) {
  return {
    data: { queues: [{ specialty: 'derma', entries: rows }] },
    status: 200,
  } as never;
}

const ROW_PATIENT_23 = {
  id: 501,
  appointment_id: 40,
  patient_id: 23,
  patient_name: 'SYNTHETIC PATIENT A',
  phone: '100',
  status: 'waiting',
  visit_id: 98,
};

const ROW_PATIENT_40 = {
  id: 502,
  appointment_id: 41,
  patient_id: 40,
  patient_name: 'SYNTHETIC PATIENT B',
  phone: '200',
  status: 'waiting',
  visit_id: 55,
};

let principalCounter = 0;

function mountPanel(initialEntry: string, rows: Array<Record<string, unknown>>) {
  principalCounter += 1;
  vi.mocked(tokenManager.getAccessToken).mockReturnValue(`deep-link-principal-${principalCounter}`);
  mockedGet.mockReset();
  mockedGet.mockImplementation(async (url: unknown) => {
    const path = String(url);
    if (path === '/registrar/queues/today') return queueResponse(rows);
    if (path === '/appointments/40/status') {
      return { data: { visit_id: 98, emr: { id: 1, is_draft: false }, prescription: null, can_create_prescription: true, can_complete: true }, status: 200 } as never;
    }
    if (path === '/appointments/41/status') {
      return { data: { visit_id: 55, emr: { id: 2, is_draft: false }, prescription: null, can_create_prescription: true, can_complete: true }, status: 200 } as never;
    }
    if (path.startsWith('/v2/emr/')) {
      return { data: { id: 3, is_draft: false, visit_id: Number(path.split('/').pop()) }, status: 200 } as never;
    }
    throw new Error(`unexpected GET ${path}`);
  });
  return renderWithProviders(
    <>
      <DermatologistPanelUnified />
      <NavigateProbe />
    </>,
    {
      routerProps: { initialEntries: [initialEntry] },
    },
  );
}

function emrEditor(): HTMLElement | null {
  return screen.queryByTestId('emr-editor');
}

describe('DERMAURL-FE-001 — contradictory patientId + visitId deep link fails closed', () => {
  it('does not open the EMR editor for a mixed pair (pre-fix: visit 77 rendered under patient 23)', async () => {
    mountPanel('/doctor/dermatology?patientId=23&visitId=77', [ROW_PATIENT_23]);

    await waitFor(() => expect(mockedGet).toHaveBeenCalledWith('/registrar/queues/today'));

    // The deep-link row matches patient 23 but belongs to visit 98 — the
    // URL pair (23, 77) must not be combined into an editor context.
    await waitFor(() => {
      expect(emrEditor()).toBeNull();
    }, { timeout: 2500 });
  });

  it('does not fabricate a synthetic patient/visit pair when no row matches (pre-fix: editor at visit 77)', async () => {
    mountPanel('/doctor/dermatology?patientId=23&visitId=77', [ROW_PATIENT_40]);

    await waitFor(() => expect(mockedGet).toHaveBeenCalledWith('/registrar/queues/today'));

    await waitFor(() => {
      expect(emrEditor()).toBeNull();
    }, { timeout: 2500 });
  });

  it('positive control: a consistent pair opens the editor with the row\'s own visit', async () => {
    mountPanel('/doctor/dermatology?patientId=23&visitId=98', [ROW_PATIENT_23]);

    const editor = await screen.findByTestId('emr-editor');
    expect(editor.getAttribute('data-visit')).toBe('98');
    expect(editor.getAttribute('data-patient')).toBe('23');
  });
});

describe('DERMAURL-FE-002 — a manual selection survives the applied deep link', () => {
  it('keeps the clinician\'s later selection instead of re-applying the URL row (pre-fix: clobbered back)', async () => {
    holder.manualPatient = {
      id: 40,
      patient_id: 40,
      visit_id: 55,
      patient_name: 'SYNTHETIC PATIENT B',
      appointment_id: 41,
    };
    mountPanel('/doctor/dermatology?patientId=23&visitId=98', [ROW_PATIENT_23, ROW_PATIENT_40]);

    // The deep link resolves first (patient 23 / visit 98).
    await screen.findByTestId('emr-editor');
    expect(emrEditor()?.getAttribute('data-patient')).toBe('23');

    // The clinician opens the patients tab (URL params persist) and
    // manually selects patient B through the patient search path.
    holder.navigate?.('/doctor/dermatology?tab=patients&patientId=23&visitId=98');
    fireEvent.click(await screen.findByTestId('patients-tab'));

    // The clinician returns to the visit tab; the editor must open
    // patient B's visit, and it must STILL be patient B after settling.
    holder.navigate?.('/doctor/dermatology?tab=visit&patientId=23&visitId=98');
    await waitFor(() => {
      expect(emrEditor()?.getAttribute('data-patient')).toBe('40');
      expect(emrEditor()?.getAttribute('data-visit')).toBe('55');
    });
    await new Promise((resolve) => { setTimeout(resolve, 150); });
    expect(emrEditor()?.getAttribute('data-patient')).toBe('40');
    expect(emrEditor()?.getAttribute('data-visit')).toBe('55');
  });
});
