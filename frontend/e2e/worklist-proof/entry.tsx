import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import ModernQueueManager from '../../src/components/queue/ModernQueueManager';
import { useDermaQueueVisit } from '../../src/pages/useDermaQueueVisit';
import { buildProviderWrapper } from '../../src/test/renderWithProviders';

const Providers = buildProviderWrapper({ skipRouter: true });
const profile = JSON.parse(sessionStorage.getItem('auth_profile') || '{}') as { doctor_id?: number };
if (!profile.doctor_id) throw new Error('Missing synthetic doctor profile');
const doctors = [{ id: profile.doctor_id, specialty: 'dermatology' }];

function WorklistProof() {
  const [result, setResult] = useState('');
  const startVisit = useDermaQueueVisit({ selectPatient: selected => setResult(JSON.stringify(selected)) });
  return <>
    <ModernQueueManager
      mode="doctor"
      doctorQueueSpecialty="dermatology"
      selectedDoctor={String(profile.doctor_id)}
      doctors={doctors}
      onStartVisit={startVisit}
    />
    <output aria-label="Started synthetic visit">{result}</output>
  </>;
}

const root = document.getElementById('root');
if (!root) throw new Error('Missing worklist proof root');
createRoot(root).render(<BrowserRouter><Providers><WorklistProof /></Providers></BrowserRouter>);
