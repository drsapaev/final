import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';

import ModernQueueManager from '../../src/components/queue/ModernQueueManager';
import { useConfirm } from '../../src/components/common/ConfirmDialog';
import { useDentistActions } from '../../src/pages/dentist/useDentistActions';
import type { UseDentistActionsParams } from '../../src/pages/dentist/useDentistActions';
import { buildProviderWrapper } from '../../src/test/renderWithProviders';

const Providers = buildProviderWrapper({ skipRouter: true });
const data = JSON.parse(sessionStorage.getItem('call_flow_proof') || '{}');
const noop = () => {};
const t = (key: string) => key;

function CompletionProof() {
  const [confirm, modal] = useConfirm();
  const [selectedPatient, setSelection] = useState<UseDentistActionsParams['selectedPatient']>({
    id: data.patient, patient_id: data.patient, doctor_queue_entry_id: data.current,
    visit_id: data.visit, patient_name: 'SYNTHETIC CURRENT',
  });
  const [busy, setLoading] = useState(false);
  const [result, setResult] = useState('');
  const actions = useDentistActions({
    tI18n: t, confirm, setLoading, selectedPatient,
    setSelectedPatient: value => setSelection(value as UseDentistActionsParams['selectedPatient']),
    handleTabChange: noop,
    ensureCanonicalVisitId: async () => data.visit,
    loadDentistryAppointments: async () => [],
    loadDentistVisitProtocolByVisitId: async () => null,
    setShowDiagnosisForm: noop, setShowVisitProtocol: noop, setShowPhotoArchive: noop,
    setShowProtocolTemplates: noop, setShowReports: noop, setShowDentalChart: noop,
    setShowTreatmentPlanner: noop, setDentalChartData: noop, setProtocolTemplateDraft: noop,
  });
  return <>
    <button disabled={busy || !selectedPatient} onClick={async () => {
      setResult(String(await actions.handleCompleteVisit({ complaint: 'SYNTHETIC' })));
    }}>Complete synthetic visit</button>
    <output aria-label="Completion outcome">{result}</output>
    {modal}
    <ToastContainer autoClose={false} />
  </>;
}

function Proof() {
  return data.mode === 'manual'
    ? <ModernQueueManager mode="doctor" doctorQueueSpecialty="dentistry"
        selectedDoctor={String(data.doctor)}
        doctors={[{ id: data.doctor, specialty: 'dentistry' }]} />
    : <CompletionProof />;
}

const root = document.getElementById('root');
if (!root || !data.doctor) throw new Error('Missing synthetic test context');
createRoot(root).render(<BrowserRouter><Providers><Proof /></Providers></BrowserRouter>);
